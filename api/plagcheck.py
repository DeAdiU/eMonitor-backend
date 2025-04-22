import ast
import difflib
import logging
import sys
import os
import uuid

# --- Language Specific Imports ---
try:
    import clang.cindex
    # Configure libclang path dynamically
    def find_libclang():
        env_path = os.environ.get('LIBCLANG_PATH')
        if env_path and os.path.exists(env_path):
            return env_path
        possible_dirs = [
            '/usr/lib', '/usr/lib64', '/usr/local/lib',
            '/usr/lib/llvm-14/lib', '/usr/lib/llvm-15/lib', '/usr/lib/llvm-16/lib',
            '/usr/lib/x86_64-linux-gnu',
            '/Library/Developer/CommandLineTools/usr/lib',  # macOS
            'C:/Program Files/LLVM/bin',  # Windows
        ]
        possible_names = [
            'libclang.so', 'libclang.so.1', 'libclang-14.so.1', 'libclang-15.so.1',
            'libclang.dylib', 'libclang.dll'
        ]
        for dir_path in possible_dirs:
            for name in possible_names:
                path = os.path.join(dir_path, name)
                if os.path.exists(path):
                    return path
        return None

    libclang_path = find_libclang()
    if libclang_path:
        try:
            clang.cindex.Config.set_library_file(libclang_path)
            # Test loading to catch version mismatches or syntax errors early
            clang.cindex.Index.create()
            logging.info(f"Using libclang path: {libclang_path}")
            CLANG_AVAILABLE = True
        except Exception as e:
            logging.warning(f"Failed to initialize libclang at {libclang_path}: {e}")
            logging.warning("Ensure Python libclang bindings match your libclang version (e.g., pip install libclang==14.0.6 for LLVM 14).")
            logging.warning("If a syntax error occurs in cindex.py, reinstall libclang or check the file for corruption.")
            CLANG_AVAILABLE = False
    else:
        logging.warning("Could not find libclang library. Set LIBCLANG_PATH environment variable or install libclang.")
        CLANG_AVAILABLE = False
except ImportError:
    logging.warning("Clang library not found (pip install libclang). C/C++ checking disabled.")
    CLANG_AVAILABLE = False
except Exception as e:
    logging.warning(f"Error configuring libclang: {e}. C/C++ checking disabled.")
    CLANG_AVAILABLE = False

try:
    import javalang
    JAVALANG_AVAILABLE = True
except ImportError:
    logging.warning("javalang library not found (pip install javalang). Java checking disabled.")
    JAVALANG_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- Python AST Normalization ---
class PythonNormalizeTransformer(ast.NodeTransformer):
    """Normalizes Python AST by renaming identifiers."""
    def __init__(self):
        super().__init__()
        self.var_map = {}
        self.func_map = {}
        self.class_map = {}
        self.arg_map = {}
        self.var_count = 0
        self.func_count = 0
        self.class_count = 0
        self.arg_count = 0
        self.defined_names = set()

    def _get_generic_name(self, name, prefix):
        target_map, counter_attr = {
            "VAR": (self.var_map, "var_count"),
            "FUNC": (self.func_map, "func_count"),
            "CLASS": (self.class_map, "class_count"),
            "ARG": (self.arg_map, "arg_count"),
        }[prefix]
        existing = self.var_map.get(name) or self.func_map.get(name) or \
                   self.class_map.get(name) or self.arg_map.get(name)
        if existing:
            return existing
        count = getattr(self, counter_attr)
        generic_name = f"{prefix}_{count}"
        target_map[name] = generic_name
        setattr(self, counter_attr, count + 1)
        return generic_name

    def visit_FunctionDef(self, node):
        self.defined_names.add(node.name)
        node.name = self._get_generic_name(node.name, "FUNC")
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node):
        self.defined_names.add(node.name)
        node.name = self._get_generic_name(node.name, "CLASS")
        self.generic_visit(node)
        return node

    def visit_arg(self, node):
        self.defined_names.add(node.arg)
        node.arg = self._get_generic_name(node.arg, "ARG")
        return node

    def visit_Name(self, node):
        original_name = node.id
        if isinstance(node.ctx, (ast.Load, ast.Store)):
            generic_name = self.func_map.get(original_name) or \
                           self.class_map.get(original_name) or \
                           self.arg_map.get(original_name)
            if generic_name:
                node.id = generic_name
            else:
                node.id = self._get_generic_name(original_name, "VAR")
                if isinstance(node.ctx, ast.Store):
                    self.defined_names.add(original_name)
        self.generic_visit(node)
        return node

def normalize_python_ast(tree):
    transformer = PythonNormalizeTransformer()
    normalized_tree = transformer.visit(tree)
    ast.fix_missing_locations(normalized_tree)
    return normalized_tree, transformer.var_map, transformer.func_map

def python_ast_to_sequence(tree):
    sequence = []
    for node in ast.walk(tree):
        node_repr = type(node).__name__
        if isinstance(node, ast.Name):
            node_repr += f"_{node.id}"
        elif isinstance(node, ast.arg):
            node_repr += f"_{node.arg}"
        elif isinstance(node, ast.FunctionDef):
            node_repr += f"_{node.name}"
        elif isinstance(node, ast.ClassDef):
            node_repr += f"_{node.name}"
        sequence.append(node_repr)
    return sequence

# --- C/C++ AST Normalization ---
class ClangNormalizer:
    def __init__(self):
        self.name_map = {}
        self.counter = 0
        self.decl_kinds = {
            clang.cindex.CursorKind.FUNCTION_DECL,
            clang.cindex.CursorKind.CXX_METHOD,
            clang.cindex.CursorKind.VAR_DECL,
            clang.cindex.CursorKind.PARM_DECL,
            clang.cindex.CursorKind.CLASS_DECL,
            clang.cindex.CursorKind.STRUCT_DECL,
            clang.cindex.CursorKind.ENUM_DECL,
            clang.cindex.CursorKind.TYPEDEF_DECL,
            clang.cindex.CursorKind.NAMESPACE,
        }
        self.ref_kinds = {
            clang.cindex.CursorKind.DECL_REF_EXPR,
            clang.cindex.CursorKind.MEMBER_REF_EXPR,
            clang.cindex.CursorKind.TYPE_REF,
            clang.cindex.CursorKind.CALL_EXPR,
        }

    def _get_generic_name(self, original_name):
        if not original_name:
            return ""
        if original_name in ['int', 'float', 'double', 'char', 'void', 'bool', 'class', 'struct',
                             'namespace', 'template', 'typename', 'std', 'cout', 'cin', 'vector',
                             'string', 'map', 'set']:
            return original_name
        if original_name not in self.name_map:
            self.name_map[original_name] = f"ID_{self.counter}"
            self.counter += 1
        return self.name_map[original_name]

    def normalize(self, cursor):
        sequence = []
        for c in cursor.walk_preorder():
            kind_name = c.kind.name
            display_name = c.spelling or ""
            normalized_name_part = ""
            if c.kind in self.decl_kinds or c.kind in self.ref_kinds:
                if display_name:
                    normalized_name = self._get_generic_name(display_name)
                    normalized_name_part = f"_{normalized_name}"
            sequence.append(f"{kind_name}{normalized_name_part}")
        return sequence

def normalize_clang_ast(cursor):
    normalizer = ClangNormalizer()
    sequence = normalizer.normalize(cursor)
    return sequence, normalizer.name_map

# --- Java AST Normalization ---
class JavaNormalizer:
    def __init__(self):
        self.name_map = {}
        self.counter = 0
        self.visited = set()

    def _get_generic_name(self, original_name):
        if not original_name or not isinstance(original_name, str):
            return original_name
        common_names = {
            'int', 'float', 'double', 'char', 'void', 'boolean', 'byte', 'short', 'long',
            'String', 'System', 'out', 'println', 'print', 'main', 'class', 'interface',
            'enum', 'public', 'private', 'protected', 'static', 'final', 'return', 'new',
            'this', 'super', 'package', 'import', 'throws', 'extends', 'implements', 'null',
            'true', 'false', 'instanceof', 'ArrayList', 'List', 'HashMap', 'Map', 'Set',
            'Integer', 'Double', 'Boolean', 'Object', 'Exception', 'Override'
        }
        if original_name in common_names:
            return original_name
        if '.' in original_name:
            parts = original_name.split('.')
            if all(part[0].islower() for part in parts if part):
                return original_name
        if original_name not in self.name_map:
            self.name_map[original_name] = f"ID_{self.counter}"
            self.counter += 1
        return self.name_map[original_name]

    def normalize_node(self, node):
        if node is None or id(node) in self.visited:
            return
        self.visited.add(id(node))

        if isinstance(node, (javalang.tree.ClassDeclaration,
                            javalang.tree.InterfaceDeclaration,
                            javalang.tree.EnumDeclaration,
                            javalang.tree.MethodDeclaration,
                            javalang.tree.ConstructorDeclaration,
                            javalang.tree.VariableDeclarator,
                            javalang.tree.FormalParameter,
                            javalang.tree.EnumConstantDeclaration)):
            if hasattr(node, 'name') and node.name:
                node.name = self._get_generic_name(node.name)

        elif isinstance(node, javalang.tree.MemberReference):
            if hasattr(node, 'member') and node.member:
                node.member = self._get_generic_name(node.member)
            if hasattr(node, 'qualifier') and node.qualifier:
                if isinstance(node.qualifier, str):
                    node.qualifier = self._get_generic_name(node.qualifier)
                elif isinstance(node.qualifier, javalang.tree.Node):
                    self.normalize_node(node.qualifier)

        elif isinstance(node, javalang.tree.MethodInvocation):
            if hasattr(node, 'member') and node.member:
                node.member = self._get_generic_name(node.member)
            if hasattr(node, 'qualifier') and node.qualifier:
                if isinstance(node.qualifier, str):
                    node.qualifier = self._get_generic_name(node.qualifier)
                elif isinstance(node.qualifier, javalang.tree.Node):
                    self.normalize_node(node.qualifier)

        elif isinstance(node, javalang.tree.Type):
            if hasattr(node, 'name') and node.name:
                if node.name[0].isupper():
                    node.name = self._get_generic_name(node.name)

        elif isinstance(node, javalang.tree.SuperMethodInvocation):
            if hasattr(node, 'member') and node.member:
                node.member = self._get_generic_name(node.member)

        elif isinstance(node, javalang.tree.ExplicitConstructorInvocation):
            if hasattr(node, 'type_name') and node.type_name:
                node.type_name = self._get_generic_name(node.type_name)

        child_attrs = [
            'annotations', 'body', 'declarations', 'type_arguments', 'arguments',
            'selectors', 'prefix_operators', 'postfix_operators', 'operators',
            'block', 'catches', 'finally_block', 'condition', 'declarators',
            'dimensions', 'expression', 'expressionl', 'expressionr', 'for_update',
            'if_true', 'if_false', 'initializer', 'label', 'left', 'right', 'operand',
            'parameters', 'resources', 'statement', 'statements', 'target', 'then_statement',
            'else_statement', 'throws', 'type', 'types', 'value', 'members', 'cases',
            'switch', 'qualifier', 'sub_type'
        ]

        for attr_name in child_attrs:
            if hasattr(node, attr_name):
                child = getattr(node, attr_name)
                if isinstance(child, javalang.tree.Node):
                    self.normalize_node(child)
                elif isinstance(child, (list, tuple)):
                    for item in child:
                        if isinstance(item, javalang.tree.Node):
                            self.normalize_node(item)
                        elif isinstance(item, tuple):
                            for sub_item in item:
                                if isinstance(sub_item, javalang.tree.Node):
                                    self.normalize_node(sub_item)

def normalize_java_ast(code):
    """Parses Java code string and returns the normalized AST and name map."""
    if not JAVALANG_AVAILABLE:
        raise ImportError("javalang library not found.")
    try:
        parsed_tree = javalang.parse.parse(code)
        normalizer = JavaNormalizer()
        normalizer.normalize_node(parsed_tree)
        return parsed_tree, normalizer.name_map
    except (javalang.tokenizer.LexerError, javalang.parser.JavaSyntaxError) as e:
        logging.error(f"Java parsing error: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error during Java normalization: {e}")
        raise

def java_ast_to_sequence(tree):
    sequence = []
    queue = [tree]
    visited_walk = set()

    while queue:
        node = queue.pop(0)
        if node is None or id(node) in visited_walk:
            continue
        visited_walk.add(id(node))

        node_repr = type(node).__name__
        name_to_add = None
        if hasattr(node, 'name') and isinstance(node.name, str) and node.name.startswith("ID_"):
            name_to_add = node.name
        elif hasattr(node, 'member') and isinstance(node.member, str) and node.member.startswith("ID_"):
            name_to_add = node.member

        if name_to_add:
            node_repr += f"_{name_to_add}"

        sequence.append(node_repr)

        children = []
        child_attrs = [
            'annotations', 'body', 'declarations', 'type_arguments', 'arguments',
            'selectors', 'prefix_operators', 'postfix_operators', 'operators',
            'block', 'catches', 'finally_block', 'condition', 'declarators',
            'dimensions', 'expression', 'expressionl', 'expressionr', 'for_update',
            'if_true', 'if_false', 'initializer', 'label', 'left', 'right', 'operand',
            'parameters', 'resources', 'statement', 'statements', 'target', 'then_statement',
            'else_statement', 'throws', 'type', 'types', 'value', 'members', 'cases',
            'switch', 'qualifier', 'sub_type'
        ]
        for attr_name in reversed(child_attrs):
            if hasattr(node, attr_name):
                child = getattr(node, attr_name)
                if isinstance(child, javalang.tree.Node):
                    children.append(child)
                elif isinstance(child, (list, tuple)):
                    for item in reversed(child):
                        if isinstance(item, javalang.tree.Node):
                            children.append(item)
                        elif isinstance(item, tuple):
                            for sub_item in reversed(item):
                                if isinstance(sub_item, javalang.tree.Node):
                                    children.append(sub_item)
        queue[0:0] = children

    return sequence

# --- Main Plag Checker Function ---
def plagchecker(code1: str, code2: str, language: str) -> float:
    """
    Compares two code snippets for similarity using AST comparison.

    Args:
        code1: First code snippet as a string.
        code2: Second code snippet as a string.
        language: Programming language ('python', 'cpp', 'java').

    Returns:
        Similarity score between 0.0 (different) and 1.0 (identical structure).
        Returns -1.0 if parsing fails or language is unsupported.
    """
    lang = language.lower()
    if not code1.strip() or not code2.strip():
        logging.error("One or both code snippets are empty.")
        return -1.0

    seq1, seq2 = None, None
    try:
        if lang == 'python':
            logging.info("Processing Python code...")
            tree1 = ast.parse(code1)
            tree2 = ast.parse(code2)
            norm_tree1, map1, _ = normalize_python_ast(tree1)
            norm_tree2, map2, _ = normalize_python_ast(tree2)
            seq1 = python_ast_to_sequence(norm_tree1)
            seq2 = python_ast_to_sequence(norm_tree2)

        elif lang in ['c', 'cpp', 'c++']:
            if not CLANG_AVAILABLE:
                logging.error("Clang library not available.")
                return -1.0
            logging.info("Processing C/C++ code...")
            index = clang.cindex.Index.create()
            unique_id = str(uuid.uuid4())
            tu1 = index.parse(f'tmp_{unique_id}_1.cpp', args=['-std=c++17'],
                             unsaved_files=[(f'tmp_{unique_id}_1.cpp', code1)],
                             options=clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)
            tu2 = index.parse(f'tmp_{unique_id}_2.cpp', args=['-std=c++17'],
                             unsaved_files=[(f'tmp_{unique_id}_2.cpp', code2)],
                             options=clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)

            errors1 = [d for d in tu1.diagnostics if d.severity >= clang.cindex.Diagnostic.Error]
            errors2 = [d for d in tu2.diagnostics if d.severity >= clang.cindex.Diagnostic.Error]
            if errors1 or errors2:
                logging.error(f"C/C++ parsing errors.")
                return -1.0
            seq1, map1 = normalize_clang_ast(tu1.cursor)
            seq2, map2 = normalize_clang_ast(tu2.cursor)

        elif lang == 'java':
            if not JAVALANG_AVAILABLE:
                logging.error("javalang library not available.")
                return -1.0
            logging.info("Processing Java code...")
            norm_tree1, map1 = normalize_java_ast(code1)
            norm_tree2, map2 = normalize_java_ast(code2)
            seq1 = java_ast_to_sequence(norm_tree1)
            seq2 = java_ast_to_sequence(norm_tree2)

        else:
            logging.error(f"Unsupported language: {language}. Use 'python', 'cpp', or 'java'.")
            return -1.0

    except (SyntaxError, javalang.tokenizer.LexerError, javalang.parser.JavaSyntaxError) as e:
        logging.error(f"Parsing error: {e}")
        return -1.0
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return -1.0

    if seq1 is None or seq2 is None:
        logging.error("Failed to generate sequences.")
        return -1.0

    matcher = difflib.SequenceMatcher(None, seq1, seq2, autojunk=False)
    similarity = matcher.ratio()
    logging.info(f"Similarity score: {similarity:.4f}")
    return similarity

