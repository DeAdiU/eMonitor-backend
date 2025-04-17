import requests
import json
from datetime import datetime
from collections import defaultdict
import collections

class CodechefAPI:
    def __init__(self, username):
        self.username = username
        self.data = self.get_data()
    
    def get_data(self):
        url = f"https://codechef-api.vercel.app/handle/{self.username}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    
    def get_rating(self):
        return { "current_rating":self.data["currentRating"], "high_rating": self.data["highestRating"] }
    
    def get_rank(self):
        return { "country_rank": self.data["countryRank"], "global_rank": self.data["globalRank"] }
    
    def get_stars(self):
        return self.data["stars"]
    
    def get_submissions_monthly(self):
        heatmap_data_list = self.data["heatMap"]
        monthly_counts = defaultdict(int)
        if not isinstance(heatmap_data_list, list):
            print("Warning: Invalid heatmap_data_list provided.")
            return {}

        for entry in heatmap_data_list:
            try:
                date_str = entry.get("date")
                value = int(entry.get("value", 0))
                if not date_str:
                    continue

                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                month_key = date_obj.strftime('%Y-%m')
                monthly_counts[month_key] += value
            except (ValueError, TypeError, AttributeError) as e:
                print(f"Warning: Skipping invalid heatmap entry: {entry}. Error: {e}")
                continue

        # Sort the dictionary by keys (months) before returning
        # Use OrderedDict to maintain insertion order after sorting keys
        sorted_monthly_counts = collections.OrderedDict(sorted(monthly_counts.items()))
        return dict(sorted_monthly_counts)

    def get_submissions_weekly(self):
        heatmap_data_list = self.data["heatMap"]
        weekly_counts = defaultdict(int)
        if not isinstance(heatmap_data_list, list):
            print("Warning: Invalid heatmap_data_list provided.")
            return {}

        for entry in heatmap_data_list:
            try:
                date_str = entry.get("date")
                value = int(entry.get("value", 0))
                if not date_str:
                    continue

                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                iso_year, iso_week, _ = date_obj.isocalendar()
                # Format as YYYY-Www (using 'W' prefix as in your example)
                week_key = f"{iso_year}-W{iso_week:02d}"
                weekly_counts[week_key] += value
            except (ValueError, TypeError, AttributeError) as e:
                print(f"Warning: Skipping invalid heatmap entry: {entry}. Error: {e}")
                continue

        # Sort the dictionary by keys (weeks) before returning
        sorted_weekly_counts = collections.OrderedDict(sorted(weekly_counts.items()))
        return dict(sorted_weekly_counts)
    
    def get_ratings_graph(self):
        rating_data_list = self.data["ratingData"]
        processed_ratings = []
        if not isinstance(rating_data_list, list):
            print("Warning: Invalid rating_data_list provided.")
            return []

        for contest in rating_data_list:
            try:
                date_str = contest.get("end_date", "").split(" ")[0]
                rating = int(contest.get("rating", 0))
                datetime.strptime(date_str, '%Y-%m-%d')
                processed_ratings.append({"date": date_str, "rating": rating})
            except (ValueError, TypeError, AttributeError) as e:
                print(f"Warning: Skipping invalid rating entry: {contest}. Error: {e}")
                continue

        processed_ratings.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'))
        return processed_ratings