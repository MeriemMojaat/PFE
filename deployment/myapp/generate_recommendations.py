"""
Command‑line script to generate recommendations.
Usage examples:
  python generate_recommendations.py --client 12345
  python generate_recommendations.py --all --limit 10
  python generate_recommendations.py --all --output my_recs.csv
"""

import argparse
import json
from recommendation_engine import RecommendationEngine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", type=int, help="Single client ID to recommend for")
    parser.add_argument("--all", action="store_true", help="Generate for all clients")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of clients (when --all)")
    parser.add_argument("--output", type=str, default="recommendations.csv", help="Output CSV file")
    args = parser.parse_args()
    
    engine = RecommendationEngine()
    
    if args.client:
        recs = engine.recommend_for_client(args.client)
        print(json.dumps(recs, indent=2, ensure_ascii=False))
    elif args.all:
        engine.recommend_all_clients(limit=args.limit, output_file=args.output)
    else:
        print("Please provide --client or --all")

if __name__ == "__main__":
    main()