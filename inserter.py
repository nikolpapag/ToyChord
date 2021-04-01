import sys
import argparse
from time import time
from random import choice
from itertools import product
from flask import Flask, request, render_template, jsonify
import requests
import hashlib
import os
import threading
from time import sleep

app = Flask(__name__)

ports = [5000, 5001, 5002, 5003, 5004, 5005, 5006, 5007, 5008, 5009]


@app.route("/")
def home():
	with open('requests.txt', 'r') as f:
		# do all inserts and update log files
		lines = list(map(lambda line: line.strip('\n'), f.readlines()))
		insert_times = []
		for line in lines:
			command = line.split(', ')
			key=command[1]
			key = key.replace(' ', '_')
			insert_start = time()
			if (str(command[0])=="insert"):
				value=command[2]
				value = value.replace(' ', '_')
				requests.post("http://0.0.0.0:" + str(choice(ports)) + "/insert",data={'song_title':key, 'song_value':value})
			elif (str(command[0])=="query"):
				requests.post("http://0.0.0.0:" + str(choice(ports)) + "/search",data={'song_name':key})
			insert_end = time()
			insert_times.append(insert_end - insert_start)
		print(f'Insertions took {sum(insert_times)} seconds')
	return render_template("home.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5010, use_reloader=False)
