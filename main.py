from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase
from googletrans import Translator
from langdetect import detect

app = Flask(__name__)
app.config["SECRET_KEY"] = "hjhjsdahhds"
socketio = SocketIO(app, async_mode='eventlet')

trans = Translator()
rooms = {}

def generate_unique_code(length):
    while True:
        code = "".join(random.choice(ascii_uppercase) for _ in range(length))
        if code not in rooms:
            break
    return code

# Initial landing page
@app.route("/", methods=["GET", "POST"])
def homepage():
    session.clear()
    if request.method == "POST":
        return redirect(url_for("home"))
    return render_template("HOME1.html") 

# Secondary page to enter room details
@app.route("/home", methods=["GET", "POST"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        language = request.form.get("language")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("home.html", error="Please enter a name.", code=code, name=name)

        if join and not code:
            return render_template("home.html", error="Please enter a room code.", code=code, name=name)

        room = code
        if create:
            room = generate_unique_code(4)
            rooms[room] = {"members": {}, "messages": []}
        elif code not in rooms:
            return render_template("home.html", error="Room does not exist.", code=code, name=name)

        session["room"] = room
        session["name"] = name
        session["language"] = language
        rooms[room]["members"][name] = language
        return redirect(url_for("room"))
    return render_template("home.html")  

# Chat room page
@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))
    return render_template("room.html", code=room, messages=rooms[room]["messages"], number_of_member=len(rooms[room]["members"]))
from datetime import datetime

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return
    
    original_message = data["data"]
    sender_name = session.get("name")
    sender_language = detect(original_message)
    
    # Get the current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    translated_messages = {}

    for member_name, member_language in rooms[room]["members"].items():
        # Translate the message for each member
        translated_text = trans.translate(original_message, src=sender_language, dest=member_language).text
        translated_messages[member_name] = translated_text

        # Send the translated message to the member in the room
        send({
            "name": sender_name,
            "language": member_language,
            "message": translated_text,
            "timestamp": timestamp  # Add the timestamp here
        }, to=room)
    
    # Store the original message, its translations, and the timestamp in the room's messages
    rooms[room]["messages"].append({
        "name": sender_name,
        "original_message": original_message,
        "translations": translated_messages,
        "timestamp": timestamp  # Store the timestamp here as well
    })


@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    language = session.get("language")
    message = "has entered the room"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    send({"name": name, "message": message, "language": language,"timestamp":timestamp}, to=room)
    
    # Emit the updated number of members to all clients in the room
    number_of_members = len(rooms[room]["members"])
    socketio.emit('update_member_count', {'count': number_of_members}, room=room)

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    language = session.get("language")
    leave_room(room)
    message = "has left the room"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if room in rooms:
        del rooms[room]["members"][name]
        if len(rooms[room]["members"]) == 0:
            del rooms[room]
    send({"name": name, "message": message, "language": language,"timestamp":timestamp}, to=room)
    
    # Emit the updated number of members to all clients in the room
    number_of_members = len(rooms[room]["members"])
    socketio.emit('update_member_count', {'count': number_of_members}, room=room)


if __name__ == "__main__":
    socketio.run(app, debug=True)
