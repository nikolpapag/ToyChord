from flask import Flask, request, render_template, jsonify
import requests
import hashlib
import os
import threading
from time import sleep

app = Flask(__name__)

my_songs = []
initial_node = False
global my_port
my_port = "5007"
global my_port_hashed
my_port_hashed = hashlib.sha1(my_port.encode()).hexdigest()
global my_previous_node
my_previous_node = my_port
global my_next_node
my_next_node = my_port
global my_previous_node_hashed
my_previous_node_hashed = str(my_port_hashed)
global my_next_node_hashed
my_next_node_hashed = str(my_port_hashed)
print("i ran")

global k
k = 3
global chain_replication
chain_replication = False

global eventual_consistency
eventual_consistency = True

if (not initial_node):
    print("I got in.")
    updated_neighbours = requests.get("http://0.0.0.0:5000/node_join", data=str(my_port))
    updated_neighbours = updated_neighbours.json()
    my_previous_node = updated_neighbours["previous_neighbour"]
    my_previous_node_hashed = hashlib.sha1(my_previous_node.encode()).hexdigest()
    my_next_node = updated_neighbours["next_neighbour"]
    my_next_node_hashed = hashlib.sha1(my_next_node.encode()).hexdigest()
    if (my_previous_node_hashed > my_port_hashed):
        i_am_first = 'yes'
    else:
        i_am_first = 'no'
    songs = requests.get("http://0.0.0.0:" + my_next_node + "/update_songs",
                         data=i_am_first)  # get songs from my next node
    print("I have received my songs")
    songs = songs.json()
    songs_received = songs["send"]
    songs_received = songs_received.split("/")[1:]
    requests.get("http://0.0.0.0:" + my_next_node + "/join_replication",
                 data=str(k) + ' ' + my_previous_node_hashed + ' ' + my_port_hashed)
    # print(songs_received)
    if not my_songs:  # if you have not received any songs yet
        for i in songs_received:
            i = i.split()
            my_songs.append((i[0], i[1], i[2], i[3]))
    print(my_previous_node, my_next_node)


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/insert", methods=['POST', 'GET'])
def insert():
    global k
    if (request.method == 'POST'):
        song_title = request.form["song_title"]
        song_value = request.form["song_value"]
        key = hashlib.sha1(song_title.encode()).hexdigest()
        # check if this node is responsible for this key.
        if (((my_previous_node_hashed > my_port_hashed) and (
                key > my_previous_node_hashed or key <= my_port_hashed)) or (
                key > my_previous_node_hashed and key <= my_port_hashed)):
            song_exists = False
            print("it is mine")
            for song in my_songs:
                if song[1] == song_title:
                    song_exists = True
                    my_songs.remove(song)
                    my_songs.append((song[0], song[1], song_value, str(k)))  # update song value
                    break
            if (not song_exists):
                my_songs.append((key, song_title, song_value, str(k)))
            if (chain_replication == True and k > 1):
                copy = k - 1
                started_it = my_port
                answer = requests.get("http://0.0.0.0:" + my_next_node + "/insert_chain_replication",
                                      data=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(
                                          copy) + ' ' + started_it)
                answer = answer.json()
                if answer["found"] == "yes":  # if the song was found
                    return render_template("insert_results.html", found_song="yes")
                else:
                    return render_template("insert_results.html", found_song="no")
            elif (eventual_consistency == True and k > 1):
                data = []
                copy = k - 1
                data.append(str(key))
                data.append(song_title)
                data.append(song_value)
                data.append(str(copy))
                data.append(str(my_next_node))
                data = [data]
                t = threading.Thread(target=insert_eventual_consistency, args=data)
                t.setDaemon(False)
                t.start()
                if song_exists:  # if the song was found
                    return render_template("insert_results.html", found_song="yes")
                else:
                    return render_template("insert_results.html", found_song="no")
        else:  # else, propagate to the other nodes
            if (chain_replication == True and k > 1):
                copy = k  # here we need to check that the following request does not get forwarded until this very node.
                started_it = my_port
                answer = requests.get("http://0.0.0.0:" + my_next_node + "/insert_chain_replication",
                                      data=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(
                                          copy) + ' ' + started_it)
                answer = answer.json()
                if (answer["found"] != "yes" and answer["found"] != "no"):
                    answer = answer["found"].split()
                    key = answer[0]
                    song_title = answer[1]
                    song_value = answer[2]
                    copy = answer[3]
                    started_it = answer[4]
                    copy = int(copy)
                    if (copy > 0):
                        song_exists = False
                        for song in my_songs:
                            if song[1] == song_title:
                                song_exists = True
                                my_songs.remove(song)
                                my_songs.append((song[0], song[1], song_value, str(copy)))  # update song value
                                break
                        if (not song_exists):
                            my_songs.append((key, song_title, song_value, str(copy)))
                        if (copy > 1):
                            new_copy = copy - 1
                            answer = requests.get("http://0.0.0.0:" + my_next_node + "/insert_chain_replication",
                                                  data=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(
                                                      new_copy) + ' ' + started_it)
                            answer = answer.json()
                            if answer["found"] == "yes":
                                return render_template("insert_results.html", found_song="yes")
                            else:
                                return render_template("insert_results.html", found_song="no")
                        else:
                            print("out")
                            if (not song_exists):
                                return render_template("insert_results.html", found_song="no")
                            else:
                                return render_template("insert_results.html", found_song="yes")
                elif answer["found"] == "yes":
                    return render_template("insert_results.html", found_song="yes")
                else:
                    return render_template("insert_results.html", found_song="no")
            elif (eventual_consistency == True and k > 1):
                answer = requests.get("http://0.0.0.0:" + my_next_node + "/eventual_content",
                                      data=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(k))
                answer = answer.json()
                data = []
                copy = k - 1
                node = str(answer["next_port"])
                data.append(str(key))
                data.append(song_title)
                data.append(song_value)
                data.append(str(copy))
                data.append(node)
                data = [data]
                t = threading.Thread(target=insert_eventual_consistency, args=data)
                t.setDaemon(False)
                t.start()
                if answer["found"] == "yes":
                    return render_template("insert_results.html", found_song="yes")
                else:
                    return render_template("insert_results.html", found_song="no")
            else:
                requests.post("http://0.0.0.0:" + my_next_node + "/content",
                              data=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(k))
    return render_template("insert.html")


@app.route("/eventual_content", methods=["POST", "GET"])
def eventual_content():
    if request.method == "GET":
        new_song = request.get_data().decode('utf-8')  # new_song is a string with key + song_value
        new_song = new_song.split()
        key = new_song[0]
        song_title = new_song[1]
        song_value = new_song[2]
        song_copy = new_song[3]
        if (((my_previous_node_hashed >= my_port_hashed) and (
                key > my_previous_node_hashed or key <= my_port_hashed)) or (
                key > my_previous_node_hashed and key <= my_port_hashed)):  # if this node is responsible for this key
            song_exists = False
            print("it is mine")
            for song in my_songs:
                if song[1] == new_song[1]:
                    song_exists = True
                    my_songs.remove(song)
                    my_songs.append((song[0], song[1], song_value, str(song_copy)))  # update song value
                    break
            if (not song_exists):
                my_songs.append((key, song_title, song_value, str(song_copy)))
                return jsonify(found="no", next_port=my_next_node)
            else:
                return jsonify(found="yes", next_port=my_next_node)
        else:  # if not, then check the next node.
            answer = requests.get("http://0.0.0.0:" + my_next_node + "/eventual_content",
                                  data=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(k))
            answer = answer.json()
            return jsonify(found=answer["found"], next_port=answer["next_port"])
    return f"<h1>{my_songs}</h1>"


def insert_eventual_consistency(data):
    key = data[0]
    song_title = data[1]
    song_value = data[2]
    copy = data[3]
    node = data[4]
    send = str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(copy)
    sleep(10)
    return requests.post("http://0.0.0.0:" + str(node) + "/insert_eventual_consistency_copies", data=send)


@app.route("/insert_eventual_consistency_copies", methods=["POST", "GET"])
def insert_eventual_consistency_copies():
    if (request.method == 'POST'):
        new_song = request.get_data().decode('utf-8')  # new_song is a string with key + song_value
        new_song = new_song.split()
        key = new_song[0]
        song_title = new_song[1]
        song_value = new_song[2]
        song_copy = new_song[3]
        song_exists = False
        print("I am in port: " + str(my_port))
        for song in my_songs:
            if song[1] == song_title:
                song_exists = True
                my_songs.remove(song)
                my_songs.append((song[0], song[1], song_value, song_copy))  # update song value
                break
        if (not song_exists):
            my_songs.append((key, song_title, song_value, song_copy))
        if (int(song_copy) > 1):
            new_copy = int(song_copy) - 1
            requests.post("http://0.0.0.0:" + my_next_node + "/insert_eventual_consistency",
                          data=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(new_copy))
    # return
    return f"<h1>{my_songs}</h1>"


@app.route("/content", methods=["POST", "GET"])
def content():
    if request.method == "POST":
        new_song = request.get_data().decode('utf-8')  # new_song is a string with key + song_value
        new_song = new_song.split()
        key = new_song[0]
        song_title = new_song[1]
        song_value = new_song[2]
        song_copy = new_song[3]
        if (((my_previous_node_hashed >= my_port_hashed) and (
                key > my_previous_node_hashed or key <= my_port_hashed)) or (
                key > my_previous_node_hashed and key <= my_port_hashed)):  # if this node is responsible for this key
            song_exists = False
            print("it is mine")
            for song in my_songs:
                if song[1] == new_song[1]:
                    song_exists = True
                    my_songs.remove(song)
                    my_songs.append((song[0], song[1], song_value, str(song_copy)))  # update song value
                    break
            if (not song_exists):
                my_songs.append((key, song_title, song_value, str(song_copy)))
            else:  # if not, then check the next node.
                # print(my_next_node)
                requests.post("http://0.0.0.0:" + my_next_node + "/content",
                              data=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(k))
    return f"<h1>{my_songs}</h1>"


@app.route("/update_neighbours", methods=['POST'])
def update_neighbours():
    global my_next_node
    global my_previous_node
    global my_next_node_hashed
    global my_previous_node_hashed
    data = request.get_data().decode('utf-8')
    data = data.split()
    if (request.method == 'POST'):
        if (data[0] == "next_neighbour"):
            my_next_node = data[1]
            my_next_node_hashed = hashlib.sha1(my_next_node.encode()).hexdigest()
        if (data[0] == "previous_neighbour"):
            my_previous_node = data[1]
            my_previous_node_hashed = hashlib.sha1(my_previous_node.encode()).hexdigest()
        return f"<h1>my_previous_node: {my_previous_node} my_next_node: {my_next_node}</h1>"


@app.route("/get_my_neighbours", methods=['GET'])
def get_my_neighbours():
    return f"<h1>my_previous_node: {my_previous_node} my_next_node: {my_next_node}</h1>"


@app.route("/join_replication", methods=['GET'])
def join_replication():
    data = request.get_data().decode('utf-8')
    data = data.split()
    upper_k = data[0]
    prev_startnode_hashed = data[1]
    startnode_hashed = data[2]
    global my_songs
    songs_to_remove = []
    songs_to_append = []
    upper_k = int(upper_k)
    if (upper_k > 0):
        print("upper_k is " + str(upper_k))
        for song in my_songs:
            if (int(song[3]) < upper_k and int(song[3]) > 0):
                print("appending to songs to remove: " + song[1])
                songs_to_remove.append(song)
                if (int(song[3]) > 1):
                    songs_to_append.append((song[0], song[1], song[2],
                                            str(int(song[
                                                        3]) - 1)))  # if copy>1 then add it with copy = copy - 1, else simply remove it.
            if (int(song[3]) == upper_k):  # special case because some songs' copy will be reduced when some others' not
                if (((startnode_hashed > prev_startnode_hashed) and (
                        song[0] <= prev_startnode_hashed or song[0] > startnode_hashed)) or (
                        song[0] <= prev_startnode_hashed)):
                    print("I am in here and i will save" + song[0])
                    songs_to_remove.append(song)
                    if (upper_k > 1):
                        songs_to_append.append((song[0], song[1], song[2], str(upper_k - 1)))
        print("my_songs:")
        print(my_songs)
        print("songs_to_remove:")
        print(songs_to_remove)
        for song in songs_to_remove:
            my_songs.remove(song)
        for song in songs_to_append:
            my_songs.append(song)
        if (my_next_node_hashed == startnode_hashed):
            return jsonify(ok="ok")
        else:
            print("I will normally propagate to my next node.")
            answer = requests.get("http://0.0.0.0:" + my_next_node + "/join_replication",
                                  data=str(upper_k - 1) + ' ' + prev_startnode_hashed + ' ' + startnode_hashed)
            answer = answer.json()
            return answer
    else:
        return jsonify(ok="ok")


@app.route("/update_songs", methods=['POST', 'GET'])
def update_songs():
    global my_songs
    if (request.method == 'GET'):  # if a node gets in the chord, he needs to get his songs from his next node
        he_was_first = request.get_data().decode('utf-8')
        he_was_first = (he_was_first == 'yes')
        print("he_was_first: " + str(he_was_first))
        send = ""
        print("My previous node is: " + my_previous_node + "and i will give him his songs.")
        print("My songs at this moment are: ")
        print(my_songs)
        songs_to_remove = []
        for song in my_songs:
            key = song[0]
            copy = song[3]
            copy = int(copy)
            print("checking if this song is his: " + song[1])
            if (((he_was_first) and (key <= my_previous_node_hashed or key > my_port_hashed)) or (
                    key <= my_previous_node_hashed) or (copy != k)):
                send = send + "/" + song[0] + ' ' + song[1] + ' ' + song[2] + ' ' + song[3]
                print("I will give him this: " + song[1])
        return jsonify(send=send)


@app.route("/update_songs_on_depart", methods=['GET'])
def update_songs_on_depart():
    songs_received = request.get_data().decode('utf-8')
    songs_received = songs_received.split("/")
    startnode_hashed_next = songs_received[len(songs_received) - 1].split()[0]
    upper_k = songs_received[len(songs_received) - 1].split()[1]
    songs_received = songs_received[1:(len(songs_received) - 1)]
    print("upper_k " + upper_k)
    songs_to_remove = []
    songs_to_append = []
    send = ""
    upper_k = int(upper_k)
    if (upper_k > 0):
        if (upper_k != 1):
            for song in my_songs:
                if (int(song[3]) == 1):
                    send = send + "/" + song[0] + ' ' + song[1] + ' ' + song[2] + ' ' + song[3]
                if (int(song[3]) < upper_k):
                    songs_to_remove.append(song)
                    songs_to_append.append((song[0], song[1], song[2],
                                            str(int(song[3]) + 1)))
        for song in songs_to_remove:
            my_songs.remove(song)
        for song in songs_to_append:
            my_songs.append(song)
        for s in songs_received:
            s = s.split()
            my_songs.append((s[0], s[1], s[2], s[3]))
        if (my_next_node_hashed == startnode_hashed_next):
            return jsonify(ok="ok")
        else:
            print("I will normally propagate to my next node.")
            print(" The songs i will send are: ")
            print(send)
            answer = requests.get("http://0.0.0.0:" + my_next_node + "/update_songs_on_depart",
                                  data=send + '/' + startnode_hashed_next + ' ' + str(upper_k - 1))
            answer = answer.json()
            return answer
    else:
        return jsonify(ok="ok")


@app.route("/insert_chain_replication", methods=['POST', 'GET'])
def insert_chain_replication():
    if (request.method == 'GET'):
        global k
        data = request.get_data().decode(
            'utf-8')  # data contains of two strings: the song_title and the port of the node which started the search
        data = data.split()
        key = data[0]
        song_title = data[1]
        song_value = data[2]
        copy = data[3]
        started_it = data[4]
        print("My port is: " + my_port + " and remain " + str(copy) + " replicas")
        print("Node who started it is " + started_it)
        # check if copy>1, if copy==1->last one
        copy = int(copy)
        if (copy == k):
            print("copy is equal to k")
            if (((my_previous_node_hashed > my_port_hashed) and (
                    key > my_previous_node_hashed or key <= my_port_hashed)) or (
                    key > my_previous_node_hashed and key <= my_port_hashed)):  # if this node is responsible for this key
                print("it is mine")
                song_exists = False
                for song in my_songs:
                    if song[1] == song_title:
                        song_exists = True
                        my_songs.remove(song)
                        my_songs.append((song[0], song[1], song_value, str(copy)))  # update song value
                        break
                if (not song_exists):
                    my_songs.append((key, song_title, song_value, str(copy)))
                copy = copy - 1
                if (started_it == my_next_node):
                    print(" i am in here.")
                    return jsonify(
                        found=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(copy) + ' ' + started_it)
                else:
                    answer = requests.get("http://0.0.0.0:" + my_next_node + "/insert_chain_replication",
                                          data=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(
                                              copy) + ' ' + started_it)
                    answer = answer.json()
                    return jsonify(found=answer["found"])
            else:  # if not, then check the next node.
                answer = requests.get("http://0.0.0.0:" + my_next_node + "/insert_chain_replication",
                                      data=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(
                                          copy) + ' ' + started_it)
                answer = answer.json()
                return jsonify(found=answer["found"])
        elif (copy > 0):
            song_exists = False
            for song in my_songs:
                if song[1] == song_title:
                    song_exists = True
                    my_songs.remove(song)
                    my_songs.append((song[0], song[1], song_value, str(copy)))  # update song value
                    break
            if (not song_exists):
                my_songs.append((key, song_title, song_value, str(copy)))
            if (copy > 1):
                new_copy = copy - 1
                if (started_it == my_next_node):
                    return jsonify(
                        found=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(new_copy) + ' ' + started_it)
                else:
                    answer = requests.get("http://0.0.0.0:" + my_next_node + "/insert_chain_replication",
                                          data=str(key) + ' ' + song_title + ' ' + song_value + ' ' + str(
                                              new_copy) + ' ' + started_it)
                    answer = answer.json()
                return jsonify(found=answer["found"])
            else:
                print("out")
                if (not song_exists):
                    print("i am here!")
                    return jsonify(found="no")
                else:
                    return jsonify(found="yes")
    return f"<h1>{my_songs}</h1>"


@app.route("/search", methods=['POST', 'GET'])
def search():
    if (request.method == 'POST'):
        song_title = request.form["song_name"]
        if song_title == "*":
            all_songs = ""
            all_songs = all_songs + '/' + my_port  # /5003 Radioactive,7658 flaksd,flakdj alskdfjk,akfd/5001
            for song in my_songs:
                all_songs = all_songs + ' ' + '(' + song[1] + ',' + song[2] + ')'
            answer = requests.get("http://0.0.0.0:" + my_next_node + "/all_search", data=all_songs)
            answer = answer.json()
            return render_template("query_results.html", found_song_value=answer["all_songs_all_nodes"],
                                   found_song_title="*", found_song="yes")
        else:
            key = hashlib.sha1(song_title.encode()).hexdigest()
            song_exists = False
            for song in my_songs:
                if song[1] == song_title:
                    song_exists = True
                    value_of_song_found = song[2]
                    copy_of_song_found = song[3]
                    break
            if (song_exists):
                if (eventual_consistency == True):
                    return render_template("query_results.html", found_song_value=value_of_song_found,
                                           found_song_title=song_title, found_song="yes")
                else:
                    if (int(copy_of_song_found) > 1):
                        answer = requests.get("http://0.0.0.0:" + my_next_node + "/search_from_node",
                                              data=song_title + ' ' + my_port)
                    else:
                        return render_template("query_results.html", found_song_value=value_of_song_found,
                                               found_song_title=song_title, found_song="yes")
            else:
                if (my_next_node != my_port):
                    answer = requests.get("http://0.0.0.0:" + my_next_node + "/search_from_node",
                                          data=song_title + ' ' + my_port)
                else:
                    return render_template("query_results.html", found_song_value=answer["value_of_song_found"],
                                           found_song_title=answer["song_title"], found_song="no")
            answer = answer.json()
            if answer["found"] == "yes":  # if the song was found
                return render_template("query_results.html", found_song_value=answer["value_of_song_found"],
                                       found_song_title=answer["song_title"], found_song="yes")
            else:
                return render_template("query_results.html", found_song_title=answer["song_title"], found_song="no")
    return render_template("search.html")


@app.route("/search_from_node", methods=['POST', 'GET'])
def search_from_node():
    if (request.method == 'GET'):
        data = request.get_data().decode(
            'utf-8')  # data contains of two strings: the song_title and the port of the node which started the search
        data = data.split()
        song_title = data[0]
        source_node_port = data[1]
        if song_title == "*":
            all_songs = []
        else:
            key = hashlib.sha1(song_title.encode()).hexdigest()
            song_exists = False
            for song in my_songs:
                if song[1] == song_title:
                    song_exists = True
                    value_of_song_found = song[2]
                    copy_of_song_found = song[3]
                    break
            if (song_exists):
                if (eventual_consistency == True):
                    print("copy" + copy_of_song_found)
                    return jsonify(value_of_song_found=value_of_song_found, song_title=song_title, found="yes")
                else:
                    if (int(copy_of_song_found) > 1):
                        answer = requests.get("http://0.0.0.0:" + my_next_node + "/search_from_node",
                                              data=song_title + ' ' + source_node_port)
                    else:
                        print("copy" + copy_of_song_found)
                        return jsonify(value_of_song_found=value_of_song_found, song_title=song_title, found="yes")
            else:
                if (my_next_node != source_node_port):
                    answer = requests.get("http://0.0.0.0:" + my_next_node + "/search_from_node",
                                          data=song_title + ' ' + source_node_port)
                else:
                    return jsonify(value_of_song_found="none", song_title=song_title, found="no")
        answer = answer.json()
        return answer


@app.route("/all_search", methods=['POST', 'GET'])
def all_search():
    if (request.method == 'GET'):
        data = request.get_data().decode('utf-8')  # data contains a list of all songs in all nodes
        data = data + '/' + my_port  # /5003 Radioactive,7658 flaksd,flakdj alskdfjk,akfd/5000.....
        for song in my_songs:
            data = data + ' ' + '(' + song[1] + ',' + song[2] + ')'
        nodes = data.split("/")
        nodes = nodes[1:]
        node_who_started_it = nodes[0].split()[0]  # get first node in the string
        if (
                node_who_started_it == my_next_node):  # if the node ahead of you started it, then return all the songs, else, add your songs and propagate the message
            return jsonify(all_songs_all_nodes=data)
        else:
            answer = requests.get("http://0.0.0.0:" + my_next_node + "/all_search",
                                  data=data)  # replace with next node in the future.
            answer = answer.json()
            return answer
    return render_template("search.html")


@app.route("/delete", methods=['POST', 'GET'])
def delete():
    global k
    if (request.method == 'POST'):
        song_title = request.form["song_title"]
        key = hashlib.sha1(song_title.encode()).hexdigest()
        # check if this node is responsible for this key.
        if (((my_previous_node_hashed > my_port_hashed) and (
                key > my_previous_node_hashed or key <= my_port_hashed)) or (
                key > my_previous_node_hashed and key <= my_port_hashed)):
            song_exists = False
            print("it is mine")
            for song in my_songs:
                if song[1] == song_title:
                    song_exists = True
                    my_songs.remove(song)
                    break
            if (not song_exists):
                return render_template("delete_results.html", found_song="no")
            if (chain_replication == True and k > 1):
                copy = k - 1
                started_it = my_port
                answer = requests.get("http://0.0.0.0:" + my_next_node + "/delete_chain_replication",
                                      data=str(key) + ' ' + song_title + ' ' + str(
                                          copy) + ' ' + started_it)
                answer = answer.json()
                if answer["found"] == "yes":  # if the song was found
                    return render_template("delete_results.html", found_song="yes")
                else:
                    return render_template("delete_results.html", found_song="no")
            if (eventual_consistency == True and k > 1):
                data = []
                copy = k - 1
                data.append(str(key))
                data.append(song_title)
                data.append(str(copy))
                data.append(str(my_next_node))
                data = [data]
                t = threading.Thread(target=delete_eventual_consistency, args=data)
                t.setDaemon(False)
                t.start()
                if song_exists:  # if the song was found
                    return render_template("delete_results.html", found_song="yes")
                else:
                    return render_template("delete_results.html", found_song="no")
        else:  # else, propagate to the other nodes
            if (chain_replication == True and k > 1):
                copy = k  # here we need to check that the following request does not get forwarded until this very node.
                started_it = my_port
                answer = requests.get("http://0.0.0.0:" + my_next_node + "/delete_chain_replication",
                                      data=str(key) + ' ' + song_title + ' ' + str(
                                          copy) + ' ' + started_it)
                answer = answer.json()
                if (answer["found"] != "yes" and answer["found"] != "no"):
                    answer = answer["found"].split()
                    key = answer[0]
                    song_title = answer[1]
                    copy = answer[2]
                    started_it = answer[3]
                    copy = int(copy)
                    if (copy > 0):
                        song_exists = False
                        for song in my_songs:
                            if song[1] == song_title:
                                song_exists = True
                                my_songs.remove(song)
                                break
                        if (copy > 1):
                            new_copy = copy - 1
                            answer = requests.get("http://0.0.0.0:" + my_next_node + "/delete_chain_replication",
                                                  data=str(key) + ' ' + song_title + ' ' + str(
                                                      new_copy) + ' ' + started_it)
                            answer = answer.json()
                            if (answer["found"] == "no"):
                                return render_template("delete_results.html",
                                                       found_song="no")  # we probably never end up here
                            else:
                                return render_template("delete_results.html", found_song="yes")
                        else:
                            print("out")
                            if (not song_exists):
                                return render_template("delete_results.html", found_song="no")
                            else:
                                return render_template("delete_results.html", found_song="yes")
                elif answer["found"] == "yes":
                    return render_template("delete_results.html", found_song="yes")
                else:
                    return render_template("delete_results.html", found_song="no")
            elif (eventual_consistency == True and k > 1):
                answer = requests.get("http://0.0.0.0:" + my_next_node + "/eventual_del_content",
                                      data=str(key) + ' ' + song_title + ' ' + str(k))
                answer = answer.json()
                data = []
                copy = k - 1
                node = str(answer["next_port"])
                data.append(str(key))
                data.append(song_title)
                data.append(str(copy))
                data.append(node)
                data = [data]
                t = threading.Thread(target=delete_eventual_consistency, args=data)
                t.setDaemon(False)
                t.start()
                if answer["found"] == "yes":
                    return render_template("delete_results.html", found_song="yes")
                else:
                    return render_template("delete_results.html", found_song="no")
            else:
                requests.get("http://0.0.0.0:" + my_next_node + "/del_content",
                             data=song_title + ' ' + my_port)
    return render_template("delete.html")


@app.route("/eventual_del_content", methods=["POST", "GET"])
def eventual_del_content():
    if request.method == "GET":
        new_song = request.get_data().decode('utf-8')  # new_song is a string with key + song_value
        new_song = new_song.split()
        key = new_song[0]
        song_title = new_song[1]
        song_copy = new_song[2]
        if (((my_previous_node_hashed >= my_port_hashed) and (
                key > my_previous_node_hashed or key <= my_port_hashed)) or (
                key > my_previous_node_hashed and key <= my_port_hashed)):  # if this node is responsible for this key
            song_exists = False
            print("it is mine")
            for song in my_songs:
                if song[1] == new_song[1]:
                    song_exists = True
                    my_songs.remove(song)
                    break
            if (not song_exists):
                return jsonify(found="no", next_port=my_next_node)
            else:
                return jsonify(found="yes", next_port=my_next_node)
        else:  # if not, then check the next node.
            answer = requests.get("http://0.0.0.0:" + my_next_node + "/eventual_del_content",
                                  data=str(key) + ' ' + song_title + ' ' + str(k))
            answer = answer.json()
            return jsonify(found=answer["found"], next_port=answer["next_port"])
    return f"<h1>{my_songs}</h1>"


def delete_eventual_consistency(data):
    key = data[0]
    song_title = data[1]
    copy = data[2]
    node = data[3]
    send = str(key) + ' ' + song_title + ' ' + str(copy)
    sleep(10)
    return requests.post("http://0.0.0.0:" + str(node) + "/delete_eventual_consistency_copies", data=send)


@app.route("/delete_eventual_consistency_copies", methods=["POST", "GET"])
def delete_eventual_consistency_copies():
    if (request.method == 'POST'):
        new_song = request.get_data().decode('utf-8')  # new_song is a string with key + song_value
        new_song = new_song.split()
        key = new_song[0]
        song_title = new_song[1]
        song_copy = new_song[2]
        print("I am in port: " + str(my_port))
        for song in my_songs:
            if song[1] == song_title:
                song_exists = True
                my_songs.remove(song)
                break
        if (int(song_copy) > 1):
            new_copy = int(song_copy) - 1
            requests.post("http://0.0.0.0:" + my_next_node + "/delete_eventual_consistency",
                          data=str(key) + ' ' + song_title + ' ' + str(new_copy))
    return f"<h1>{my_songs}</h1>"


@app.route("/delete_chain_replication", methods=['POST', 'GET'])
def delete_chain_replication():
    if (request.method == 'GET'):
        global k
        data = request.get_data().decode(
            'utf-8')  # data contains of two strings: the song_title and the port of the node which started the search
        data = data.split()
        key = data[0]
        song_title = data[1]
        copy = data[2]
        started_it = data[3]
        print("My port is: " + my_port + " and remain " + copy + " replicas")
        print("Node who started it is " + started_it)
        # check if copy>1, if copy==1->last one
        copy = int(copy)
        if (copy == k):
            print("copy is equal to k")
            if (((my_previous_node_hashed > my_port_hashed) and (
                    key > my_previous_node_hashed or key <= my_port_hashed)) or (
                    key > my_previous_node_hashed and key <= my_port_hashed)):  # if this node is responsible for this key
                print("it is mine")
                song_exists = False
                for song in my_songs:
                    if song[1] == song_title:
                        song_exists = True
                        my_songs.remove(song)
                        break
                if (not song_exists):
                    return jsonify(found="no")
                copy = copy - 1
                if (started_it == my_next_node):
                    print(" i am in here.")
                    return jsonify(
                        found=str(key) + ' ' + song_title + ' ' + str(copy) + ' ' + started_it)
                else:
                    answer = requests.get("http://0.0.0.0:" + my_next_node + "/delete_chain_replication",
                                          data=str(key) + ' ' + song_title + ' ' + str(
                                              copy) + ' ' + started_it)
                    answer = answer.json()
                    return jsonify(found=answer["found"])
            else:  # if not, then check the next node.
                answer = requests.get("http://0.0.0.0:" + my_next_node + "/delete_chain_replication",
                                      data=str(key) + ' ' + song_title + ' ' + str(
                                          copy) + ' ' + started_it)
                answer = answer.json()
                return jsonify(found=answer["found"])
        elif (copy > 0):
            song_exists = False
            for song in my_songs:
                if song[1] == song_title:
                    song_exists = True
                    my_songs.remove(song)
                    break
            if (copy > 1):
                new_copy = copy - 1
                if (started_it == my_next_node):
                    return jsonify(
                        found=str(key) + ' ' + song_title + ' ' + str(new_copy) + ' ' + started_it)
                else:
                    answer = requests.get("http://0.0.0.0:" + my_next_node + "/delete_chain_replication",
                                          data=str(key) + ' ' + song_title + ' ' + str(
                                              new_copy) + ' ' + started_it)
                    answer = answer.json()
                return jsonify(found=answer["found"])
            else:
                print("out")
                if (not song_exists):
                    print("i am here!")
                    return jsonify(found="no")
                else:
                    return jsonify(found="yes")
    return f"<h1>{my_songs}</h1>"


@app.route("/del_content", methods=["POST", "GET"])
def del_content():
    if request.method == "GET":
        data = request.get_data().decode('utf-8')  # song is a string with key
        data = data.split()
        song_title = data[0]
        source_node_port = data[1]
        key = hashlib.sha1(song_title.encode()).hexdigest()
        if (((my_previous_node_hashed >= my_port_hashed) and (
                key > my_previous_node_hashed or key <= my_port_hashed)) or (
                key > my_previous_node_hashed and key <= my_port_hashed)):  # if this node is responsible for this key
            song_exists = False
            for song in my_songs:
                if song[1] == song_title:
                    song_exists = True
                    my_songs.remove(song)
                    break
            if (not song_exists):
                return jsonify(song_title=song_title, found="no")
            else:
                return jsonify(song_title=song_title, found="yes")
        else:  # if not, then check the next node.
            # requests.post("http://0.0.0.0:5000/del_content", data = song_title)
            answer = requests.get("http://0.0.0.0:" + my_next_node + "/del_content",
                                  data=song_title + ' ' + source_node_port)
            return answer
    return render_template("delete.html")


@app.route("/overlay")
def overlay():
    chord_nodes_port_string = requests.get("http://0.0.0.0:5000/overlay_content")
    chord_nodes_port_string = chord_nodes_port_string.json()
    chord_nodes_port_string = chord_nodes_port_string["chord_nodes_port_string"]
    chord_nodes_port = chord_nodes_port_string.split()
    # chord_nodes_port.reverse()
    return render_template("network_overlay.html", nodes=chord_nodes_port)


@app.route("/help")
def help():
    return render_template("help.html")


@app.route("/depart", methods=["POST", "GET"])
def depart():
    global my_songs
    if request.method == "POST":
        requests.get("http://0.0.0.0:5000/node_depart", data=str(my_port))
        send = ""
        songs_to_remove = []
        for song in my_songs:
            if (int(song[3]) == 1):
                send = send + "/" + song[0] + ' ' + song[1] + ' ' + song[2] + ' ' + song[3]
        print("In depart i will send him that: ")
        print(send)
        requests.get("http://0.0.0.0:" + my_next_node + "/update_songs_on_depart",
                     data=send + "/" + my_next_node_hashed + ' ' + str(k))
        os._exit(os.EX_OK)
    return render_template("depart.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5007, use_reloader=False)
