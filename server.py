import argparse
import logging

import time
from flask import Flask, request, jsonify
from loader import MovieLensLoader, PostgresLoader
from recs import SVDBasedCF, UserBasedNNCF

app = Flask(__name__)


@app.route("/rest/<user_id>/recommend", methods=['GET', 'POST'])
def recommend(user_id):
    interests = rs.predict_interests(user_id)
    predicted_interpretation = [(x, ldr.get_item_description(x)) for x in interests]
    response = {
        "recommendations": predicted_interpretation,
    }
    return jsonify(response)


@app.route("/rest/<user_id>/history", methods=['GET', 'POST'])
def show_history(user_id):
    historical_records = [ldr.get_item_description(x.item_id) + " rated with " + str(x.rating)
                          for x in rs.user_histories.get(user_id, [])]
    response = {
        "history": historical_records,
    }
    return jsonify(response)


@app.route("/rest/<user_id>/<item_id>/rate", methods=['POST'])
def rate(user_id, item_id):
    try:
        rating = float(request.args.get("rating", "5.0"))
        ldr.put_record(item_id, user_id, rating, int(time.time()))
        rs.add_data(user_id, item_id, rating=rating)
        rs.online_update_step(user_id, item_id)
        return jsonify({'ok': True})
    except Exception as e:
        logging.exception("Exception during rating")
        return jsonify({'ok': False, 'error': str(e)}), 400


@app.route("/rest/find_item/", methods=['POST', 'GET'])
def find_item():
    try:
        tokens = set(request.args.get("query", "").lower().split())
        found = {}
        for item_id, item in ldr.get_items():
            if len(set(item.name.lower().split()) & tokens) == len(tokens):
                found[item_id] = str(item) + "(" + str(len(rs.item_histories.get(item_id, set()))) + " raters)"
                if len(found) > 30:
                    break
        return jsonify(found)
    except Exception as e:
        logging.exception("Exception during search")
        return jsonify({'ok': False, 'error': str(e)}), 400


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Movie recommender engine')
    parser.add_argument("--port", default=80, help="Port for server")
    (args) = parser.parse_args()
    print("Starting up")
    # Populating recommender system with data
    ldr = PostgresLoader("postgres", "postgres", "rs_pg", 5432, "mydb")
    rs = SVDBasedCF(70)

    for r in ldr.get_records():
        rs.add_data(r.user_id, r.item_id, r.rating, r.timestamp)
    rs.build()

    print("RS knows %d users and %d items" % (len(rs.user_histories), len(rs.item_histories)))

    app.run("0.0.0.0", port=args.port)
