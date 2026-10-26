"""
    If it says executing scripts has been disabled
        Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

    To start your app..
        1. activate the virtual environment
            .venv\Scripts\Activate.ps1
        2. starting the flask app
            flask --app app run --debug

    Your app will be served at http://localhost:5000/front_page.html

"""

# flask --app app run --debug

import calendar
from datetime import datetime # use this for getting the user's date and time, used for tasks and profile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, render_template, make_response, redirect, request, session, url_for

from PIL import Image, ImageOps, UnidentifiedImageError
# Pillow is a sort of extension to help us tweak the images. Had to use AI on finding out this one, sadly.

import io

from flask import send_from_directory # For logo and image loading

# This dude gives us space to hold what we want in an SQL table like an image and compress it.

from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

currentdirectory = "/var/data"
    
def initialize_user_settings():
    database_tables = {
        "user_settings.db": """
            CREATE TABLE IF NOT EXISTS user_settings (
                username TEXT NOT NULL,
                wallpaper_img BLOB,
                wallpaper_setting TEXT,
                public_email TEXT,
                pronouns TEXT,
                bio TEXT,
                job TEXT,
                location TEXT,
                timezone TEXT,
                account_creation_day TEXT
            )
        """,
        "profile.db": """
            CREATE TABLE IF NOT EXISTS profile (
                username TEXT,
                password TEXT,
                profile_picture BLOB
            )
        """,
        "user_holes.db": """
            CREATE TABLE IF NOT EXISTS user_holes (
                username TEXT NOT NULL,
                total_holes_dug INT
            )
        """,
        "global_holes.db": """
            CREATE TABLE IF NOT EXISTS global_holes (
                unique_test TEST UNIQUE,
                total_global_holes INT
            )
        """,
        "tasks_reloader.db": """
            CREATE TABLE IF NOT EXISTS tasks_reloader (
                username TEXT NOT NULL,
                task TEXT,
                skill TEXT,
                recurrence TEXT,
                every_month_day INT
            )
        """,
        "skills.db": """
            CREATE TABLE IF NOT EXISTS skills (
                username TEXT NOT NULL,
                skill TEXT,
                total_holes_dug INT
            )
        """,
        "tasks_today.db": """
            CREATE TABLE IF NOT EXISTS tasks_today (
                username TEXT NOT NULL,
                task TEXT,
                skill TEXT,
                day_of_month_added TEXT
            )
        """,
        "tasks_completed_today.db": """
            CREATE TABLE IF NOT EXISTS tasks_completed_today (
                username TEXT NOT NULL,
                task TEXT,
                skill TEXT,
                day_of_month_completed TEXT
            )
        """,
        "requests.db": """
            CREATE TABLE IF NOT EXISTS requests (
                sender TEXT NOT NULL,
                receiver TEXT
            )
        """,
        "friends.db": """
            CREATE TABLE IF NOT EXISTS friends (
                username TEXT NOT NULL,
                receiver TEXT
            )
        """,
        "achievements.db": """
            CREATE TABLE IF NOT EXISTS achievements (
                username TEXT NOT NULL,
                achievement TEXT
            )
        """
    }

    for database_name, create_table_sql in database_tables.items():
        database_path = os.path.join(currentdirectory, database_name)

        with sqlite3.connect(database_path) as connection:
            table_name = create_table_sql.split("EXISTS ")[1].split(" (")[0]
            connection.execute(create_table_sql)

            columns = [
                row[1] for row in connection.execute(
                    f"PRAGMA table_info({table_name})"
                ).fetchall()
            ]

            if table_name == "user_settings":
                if "timezone" not in columns:
                    connection.execute(
                        "ALTER TABLE user_settings ADD COLUMN timezone TEXT"
                    )

                if "account_creation_day" not in columns:
                    connection.execute(
                        "ALTER TABLE user_settings ADD COLUMN account_creation_day TEXT"
                    )

            print(
                f"Initialized {database_name}:",
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            )

initialize_user_settings()

def get_wallpaper_setting(username):
    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        result = connection.execute(
            "SELECT wallpaper_setting FROM user_settings WHERE username = ?",
            (username,)
        ).fetchone()

    return result[0] if result else "dark"

def get_connection_for_profile():
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "profile.db")
    )
    cursor = connection.cursor()
    return connection, cursor

app = Flask(__name__, static_folder="frontend", static_url_path="")

app.secret_key = os.environ.get("SECRET_KEY", "local-development-key")

@app.route("/static/<filename>")
def serve_static_image(filename):
    return send_from_directory(
        os.path.join(currentdirectory, "static"),
        filename
    )
@app.route("/save_timezone", methods=["POST"])
def save_timezone():
    user = session.get("user")

    if not user:
        return redirect('/')
    data = request.get_json(silent=True) or {}
    timezone = data.get("timezone")
    print("Received JSON:", data)
    print("Received timezone:", repr(timezone))
    if not isinstance(timezone, str):
        return {"error": "Invalid timezone"}, 400

    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return {"error": "Invalid timezone"}, 400

    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        connection.execute(
            "UPDATE user_settings SET timezone = ? WHERE username = ?",
            (timezone, user["username"])
        )

    return {"message": "Timezone saved"}, 200

@app.context_processor
def inject_wallpaper():
    user = session.get("user")

    if not user:
        return {
            "wallpaper_class": "dark",
            "wallpaper_url": None
        }

    wallpaper_class = get_wallpaper_setting(user["username"])

    wallpaper_url = None

    if wallpaper_class == "custom":
        wallpaper_url = url_for(
            "get_wallpaper_picture",
            username=user["username"]
        )

    return {
        "wallpaper_class": wallpaper_class,
        "wallpaper_url": wallpaper_url
    }

@app.route("/")
def home_page_blank():
    user = session.get("user")

    if user:
        return redirect("/home_page")

    return render_template("front_page.html")

@app.route("/sign_up", methods=["POST"])
def sign_up():
    username = request.form["username"]
    password = request.form["password"]
    confirm_password = request.form["confirm_password"]
    message = "" # message is blank every rerun?
    # Checks if username is null or password.
    default_image = Image.open(
        os.path.join(currentdirectory, "static", "goal_mole_placeholder.png")
    )
    inputs = [username, password, confirm_password]

    default_image = ImageOps.fit(default_image, (500, 500)) # Centers and crops the image.

    default_image = default_image.convert("RGB")

    default_image_bytes = io.BytesIO()
    default_image.save(default_image_bytes, format="JPEG", quality=80)
    """
        These two lines look weird but the first var is just empty storage created by io. Now you save it to the default_image_bytes or the first parameter
        as a jpeg with a quality of 80.
    """
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "profile.db")
    )
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile(
            username TEXT,
            password TEXT,
            profile_picture BLOB
        )
    """)
    connection.commit()
    connection.close()

    connection = sqlite3.connect(
        os.path.join(currentdirectory, "user_holes.db")
    )
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_holes(
            username TEXT NOT NULL,
            total_holes_dug INT
        )
    """)
    connection.commit()
    connection.close()

    connection = sqlite3.connect(
        os.path.join(currentdirectory, "global_holes.db")
    )

    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_holes(
            unique_test TEST UNIQUE,
            total_global_holes INT
        )
    """)
    cursor.execute(
        "INSERT OR IGNORE INTO global_holes VALUES (?, ?)",
        ("unique_check", 0) # We use this because we only want to make one column via ignore by making a unique checker to block out any duplicate inserts.
    )
    connection.commit()
    connection.close()
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "tasks_reloader.db")
    )
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks_reloader(
            username TEXT NOT NULL,
            task TEXT,
            skill TEXT,
            recurrence TEXT,
            every_month_day INT
        )
    """)
    # Recurrence is weekday it was created or like every day or month
    connection.commit()
    connection.close()
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "skills.db")
    )
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skills(
            username TEXT NOT NULL,
            skill TEXT,
            total_holes_dug INT
        )
    """)
    connection.commit()
    connection.close()
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "tasks_today.db")
    )
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks_today(
            username TEXT NOT NULL,
            task TEXT,
            skill TEXT,
            day_of_month_added TEXT
        )
    """)
    # If it's the next day then you would check the tasks_reloader 
    # and see if the current day matches up with any task there first and then do full wipe and then reload based on weekday so the every days will be removed and re added if overdue.
    connection.commit()
    connection.close()
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "tasks_completed_today.db")
    )
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks_completed_today(
            username TEXT NOT NULL,
            task TEXT,
            skill TEXT,
            day_of_month_completed TEXT
        )
    """)
    connection.commit()
    connection.close()
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "requests.db")
    )
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requests(
            sender TEXT NOT NULL,
            receiver TEXT
        )
    """)
    connection.commit()
    connection.close()
    
    encoded_image = default_image_bytes.getvalue()

    connection = sqlite3.connect(
        os.path.join(currentdirectory, "friends.db")
    )
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS friends (
            username TEXT NOT NULL,
            receiver TEXT
        )
    """) #TODO We will have one connection with one person and another one sided and we just do a double check for each one to get each user's friends.
    connection.commit()
    connection.close()
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "achievements.db")
    )
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS achievements(
            username TEXT NOT NULL,
            achievement TEXT
        )
    """)
    connection.commit()
    connection.close()
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "user_settings.db")
    )
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            username TEXT NOT NULL,
            wallpaper_img BLOB,
            wallpaper_setting TEXT,
            public_email TEXT,
            pronouns TEXT,
            bio TEXT,
            job TEXT,
            location TEXT,
            timezone TEXT,
            account_creation_day TEXT
        )
    """) #IMPORTANT 8 Elements in here currently
    columns = [
        row[1] for row in connection.execute(
            "PRAGMA table_info(user_settings)"
        ).fetchall()
    ]

    if "account_creation_day" not in columns:
        connection.execute(
            "ALTER TABLE user_settings ADD COLUMN account_creation_day TEXT"
        )
    if "timezone" not in columns:
        connection.execute(
            "ALTER TABLE user_settings ADD COLUMN timezone TEXT"
        )
    connection.commit()
    connection.close()
    for x in range(len(inputs)):
        if not len(inputs[x]) >= 5:
            message = "Name and password must be greater than or equal to 5 characters."
            username = ""
            return render_template(
                "sign_up_page.html",
                username=username,
                password=password,
                confirm_password=confirm_password,
                message=message
            )
        if len(inputs[x]) > 15:
            message = "Name and password must be less than or equal to 15 characters."
            username = ""
            return render_template(
                "sign_up_page.html",
                username=username,
                password=password,
                confirm_password=confirm_password,
                message=message
            )
        for y in range(len(inputs[x])):
            if inputs[x][y] == " ":
                if x == 0:
                    placeholder_message = "username"
                    username = ""
                elif x == 1:
                    placeholder_message = "password"
                    password = ""
                    confirm_password = ""
                elif x == 2:
                    placeholder_message = "confirmed password"
                    confirm_password = ""
                message = f"Your {placeholder_message} must contain no spaces."
                return render_template(
                    "sign_up_page.html",
                    username=username,
                    password=password,
                    confirm_password=confirm_password,
                    message=message
                )

        # Space checker.
    
    connection, cursor = get_connection_for_profile()

    cursor.execute(
        "SELECT * FROM profile WHERE username = ?",
        (username,)
    )
    # gets the inputted username and has to have the comma because it's a tuple. 
    user = cursor.fetchone()
    # gets the first row that appears. You can also use these to do the sign up.
    if not user and password == confirm_password:
        timezone = request.form.get("timezone") or "UTC"

        try:
            current_time = datetime.now(ZoneInfo(timezone))
        except (ZoneInfoNotFoundError, ValueError):
            timezone = "UTC"
            current_time = datetime.now(ZoneInfo("UTC"))

        current_date = current_time.date().isoformat()

        connection = sqlite3.connect(
            os.path.join(currentdirectory, "user_settings.db")
        )
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO user_settings VALUES (?, ?, ?, ?, ? ,?, ?, ?, ?, ?)",
            (username, "", "dark", "", "", "", "", "", timezone, current_date) # CURRENT DATE SHOWS +1 DAY TODO FIX
            # dark is the background setting and username is the user and the "" is the image we are working with, the other stuff are "" because it is blank when first initialized
        )
        connection.commit()
        connection.close()
        # Username doesn't exist
        # Cursor is what you use to send commands to the database
        hashed_password = generate_password_hash(password)
        connection = sqlite3.connect(
            os.path.join(currentdirectory, "user_holes.db")
        )
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO user_holes VALUES (?, ?)",
            (username, 0)
        )
        connection.commit()
        connection.close()

        connection = sqlite3.connect(
            os.path.join(currentdirectory, "profile.db")
        )
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO profile VALUES (?, ?, ?)",
            (username, hashed_password, encoded_image)
        )
        """query = "INSERT INTO profile VALUES ('{username}','{password}')".format(
            username=username,
            password=password
        )""" # This dude here can be vulnerable to SQL injection attacks. 
        # stores the command I want to run. 
        connection.commit()
        # internalizes this command into the table so when you leave it
        session["user"] = {
            "username": username
        }
        connection.close()
        # Give us the username as a session so it can remain logged in and can be used.

        return redirect("/")
    elif password != confirm_password:
        message = "Please make sure that your confirmed password matches your password."
        password = ""
        confirm_password = ""
        connection.close()
        return render_template(
            "sign_up_page.html",
            username=username,
            message=message
        )
    elif user:
        message = "Username already exists."
        username = ""
        connection.close() # All these closes are here to save memory and to close the usage of the database the pc is using up to keep the database active. 
        # These operations only run because you click the submit button. So mid input it pauses the database to stop potential daddy issues. 
        return render_template(
            "sign_up_page.html",
            username=username,
            password=password,
            confirm_password=confirm_password,
            message=message
        )



@app.route("/sign_up", methods=["GET"])
def sign_up_page(): 
    return render_template("sign_up_page.html") # when they reach the address "/sign_up" they must go to the sign up page immediately. 
        
@app.route("/sign_in", methods=["GET"])
def sign_in_page():
    return render_template("sign_in_page.html")

@app.route("/sign_in", methods=["POST"])
def post_sign_in():
    username = request.form.get("username")
    password = request.form.get("password")
    sign_in_message = request.form.get("sign_in_message")

    connection = sqlite3.connect(os.path.join(currentdirectory, "profile.db"))
    cursor = connection.cursor()
    cursor.execute(
        "SELECT password FROM profile WHERE username = ?",
        (username,)
    )

    user_exists = cursor.fetchone()

    if not user_exists:
        username = ""
        sign_in_message = "Username does not exist, consider signing in."
        connection.close()
        return render_template(
            "sign_in_page.html",
            sign_in_message=sign_in_message,
            username=username
        )
    pwd_valid = check_password_hash(user_exists[0], password)
    if not pwd_valid:
        # user_exists[0] here gets the first value in the row, or it gets the first column. 
        sign_in_message = "Username or Password is incorrect."
        connection.close()
        return render_template(
            "sign_in_page.html",
            sign_in_message=sign_in_message,
            username=username
        )
    
    resp = redirect("/")
    # resp.set_cookie("username", username, httponly=True, max_age=60*60*24*7)
    session["user"] = {
        "username": username
    }
    connection.close()
    return resp


@app.route("/profile_picture/<username>")
def get_profile_picture(username):
    # This runs a function that decodes the SQL PFP.
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "profile.db")
    )
    
    cursor = connection.cursor()
    cursor.execute(
        "SELECT profile_picture FROM profile WHERE username = ?",
        (username,)
    )
    result = cursor.fetchone()

    if not result or not result[0]:
        connection.close()
        return "Profile picture not found", 404

    profile_picture = result[0]
    connection.close()
    # 0 here just gets the value rather than key and value.
    return profile_picture, 200, {"Content-Type": "image/jpeg"}
    # 200 is the value that means that everything worked out and third item tells flask what kind of item we are sending and the browser read and decodes it. 

@app.route("/log_out")
def log_out():
    session.clear()
    # Logs us out and brings us to the front page. The user is not deleted in the database.
    return redirect("/")


@app.route("/people_search", methods=["GET", "POST"])
def people_search():
    user = session.get("user")

    if not user:
        return redirect("/")
    text = request.values.get("input_search", "").strip().lower()

    people = []
    requests_sent = []
    friends = []
    if text:
        with sqlite3.connect(os.path.join(currentdirectory, "profile.db")) as connection_profile:
            connection_profile.row_factory = sqlite3.Row
            people = connection_profile.execute(
                "SELECT username, profile_picture FROM profile WHERE username LIKE ? AND username != ?",
                (f"{text}%", user['username'])
            ).fetchall()

        with sqlite3.connect(os.path.join(currentdirectory, "requests.db")) as connection_requests:
            connection_requests.row_factory = sqlite3.Row
            requests_sent = connection_requests.execute(
                "SELECT receiver FROM requests WHERE sender = ?",
                (user["username"],)
            ).fetchall()

        requests_sent = [row["receiver"] for row in requests_sent]
        with sqlite3.connect(os.path.join(currentdirectory, "friends.db")) as connection_friends:
            connection_friends.row_factory = sqlite3.Row
            friends_dict = connection_friends.execute(
                "SELECT * FROM friends WHERE receiver = ? OR username = ?",
                (user["username"], user["username"])
            ).fetchall()
        for friend in friends_dict:
            if friend["username"] == user["username"] and friend["receiver"]:
                friends.append(friend["receiver"])
            elif friend["receiver"] == user["username"] and friend["username"]:
                friends.append(friend["username"])    # This will turn the whole jumble dict into a bunch of names.
    return render_template(
        "people_search.html",
        user=user,
        username=user["username"],
        people=people,
        search=text,
        requests_sent=requests_sent,
        friends=friends
    )

@app.route("/friend_requesting", methods=["POST"])
def friend_requesting():
    user = session.get("user")
    if not user:
        return redirect("/")

    selected_user = request.form.get("user")

    with sqlite3.connect(os.path.join(currentdirectory, "requests.db")) as connection:
        connection.execute(
            "INSERT INTO requests VALUES (?, ?)",
            (user["username"], selected_user)
        )
    return redirect(request.referrer or "/people_search")

@app.route("/friend_requests", methods=["GET"])
def get_requests():
    user = session.get("user")
    if not user:
        return redirect("/")
    with sqlite3.connect(os.path.join(currentdirectory, "requests.db")) as connection_requests:
        connection_requests.row_factory = sqlite3.Row
        requests = connection_requests.execute(
            "SELECT sender FROM requests WHERE receiver = ?",
            (user["username"],)
        ).fetchall()
    return render_template(
        "friend_requests.html",
        user=user,
        requests=requests
    )
@app.route("/accept_request", methods=["POST"])
def accept_request():
    user = session.get("user")
    sender = request.form.get("sender")
    if not user:
        return redirect("/")
    if not sender:
        return redirect("/friend_requests")
    with sqlite3.connect(os.path.join(currentdirectory, "friends.db")) as connection_friends:
        connection_friends.row_factory = sqlite3.Row
        friends = connection_friends.execute(
            "SELECT * FROM friends WHERE receiver = ? OR username = ?",
            (user["username"], user["username"])
        ).fetchall()
    names = []
    for friend in friends:
        if friend["username"] == user["username"] and friend["receiver"]:
            names.append(friend["receiver"])
        elif friend["receiver"] == user["username"] and friend["username"]:
            names.append(friend["username"])    # This will turn the whole jumble dict into a bunch of names.
    friend_count = len(names)
    if friend_count >= 200:
        max_friends_error_message = "Over 200 friends! Limit reached!"
        with sqlite3.connect(os.path.join(currentdirectory, "requests.db")) as connection_requests:
            connection_requests.row_factory = sqlite3.Row
            requests = connection_requests.execute(
                "SELECT sender FROM requests WHERE receiver = ?",
                (user["username"],)
            ).fetchall()

        return render_template (
            "friend_requests.html",
            user=user,
            requests=requests,
            max_friends_error_message=max_friends_error_message
        )
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "requests.db")
    )
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM requests WHERE sender = ? AND receiver = ?",
        (sender, user["username"])
    )
    connection.commit()
    connection.close()
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "friends.db")
    )
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO friends VALUES (?, ?)",
        (user["username"], sender) # TODO ONE SIDER USE THIS FOR THE people_search!
    )
    connection.commit()
    connection.close()
    return redirect("/friend_requests")

@app.route("/decline_request", methods=["POST"])
def decline_request():
    user = session.get("user")
    sender = request.form.get("sender")
    if not user:
        return redirect("/")

    connection = sqlite3.connect(
        os.path.join(currentdirectory, "requests.db")
    )
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM requests WHERE sender = ? AND receiver = ?",
        (sender, user["username"]) 
    )
    connection.commit()
    connection.close()
    return redirect("/friend_requests")

@app.route("/friends", methods=["GET"])
def get_load_friends():
    user = session.get("user")
    exist = True # check to see if any people are even in the list
    if not user:
        return redirect("/")
    with sqlite3.connect(os.path.join(currentdirectory, "friends.db")) as connection_friends:
        connection_friends.row_factory = sqlite3.Row
        friends = connection_friends.execute(
            "SELECT * FROM friends WHERE receiver = ? OR username = ?",
            (user["username"], user["username"])
        ).fetchall()
    names = []
    for friend in friends:
        if friend["username"] == user["username"] and friend["receiver"]:
            names.append(friend["receiver"])
        elif friend["receiver"] == user["username"] and friend["username"]:
            names.append(friend["username"])    # This will turn the whole jumble dict into a bunch of names.
    friend_count = len(names)
    exist = len(names) > 0
    return render_template("friends_list.html", user=user, names=names, exist=exist, friend_count=friend_count)

@app.route("/unfriend", methods=["POST"])
def unfriend_user():
    user = session.get("user")

    if not user:
        return redirect("/")

    recieved_request_origin = request.form.get("recieved_request_origin")
    with sqlite3.connect(os.path.join(currentdirectory, "friends.db")) as connection_friends:
        connection_friends.row_factory = sqlite3.Row
        connection_friends.execute(
            "DELETE FROM friends WHERE receiver = ? AND username = ? OR receiver = ? AND username = ?",
            (user["username"], recieved_request_origin, recieved_request_origin, user["username"])
        ).fetchall()
    return redirect("/friends")

@app.route("/update_profile", methods=["POST"])
def update_profile():
    user = session.get("user")

    if not user:
        return redirect("/")
    
    file = request.files.get("picture")
    if not file or file.filename == "":
        return redirect("/settings")  # they clicked the button without choosing a file
    
    try:
        image = Image.open(file.stream)
    except (UnidentifiedImageError, OSError):
        return redirect("/settings")  # file isn't an image

    image = ImageOps.exif_transpose(image)   # fixes sideways phone photos
    image = ImageOps.fit(image, (500, 500))  # same crop as sign-up
    image = image.convert("RGB")             # JPEG can't store transparency

    image_bytes = io.BytesIO()
    image.save(image_bytes, format="JPEG", quality=80)

    connection, cursor = get_connection_for_profile()
    cursor.execute(
        "UPDATE profile SET profile_picture = ? WHERE username = ?",
        (image_bytes.getvalue(), user["username"])
    )
    connection.commit()
    connection.close()

    return redirect("/settings")

@app.route("/settings", methods=["GET"])
def get_settings():
    user = session.get("user")

    if not user:
        return redirect("/") #TODO check that shi soon
    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        current_email_displayed = connection.execute(
            """
                SELECT public_email
                FROM user_settings
                WHERE username = ?
            """,
            (user["username"],)
        ).fetchone()
    if current_email_displayed:
        current_email_displayed = current_email_displayed[0]
    else:
        current_email_displayed = None

    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        current_pronouns_displayed = connection.execute(
            """
                SELECT pronouns
                FROM user_settings
                WHERE username = ?
            """,
            (user["username"],)
        ).fetchone()
    if current_pronouns_displayed:
        current_pronouns_displayed = current_pronouns_displayed[0]
    else:
        current_pronouns_displayed = None
    
    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        current_bio_displayed = connection.execute(
            """
                SELECT bio
                FROM user_settings
                WHERE username = ?
            """,
            (user["username"],)
        ).fetchone()
    if current_bio_displayed:
        current_bio_displayed = current_bio_displayed[0]
    else:
        current_bio_displayed = None
    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            current_job_displayed = connection.execute(
                """
                    SELECT job
                    FROM user_settings
                    WHERE username = ?
                """,
                (user["username"],)
            ).fetchone()
    if current_job_displayed:
        current_job_displayed = current_job_displayed[0]
    else:
        current_job_displayed = None
    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        current_location_displayed = connection.execute(
            """
                SELECT location
                FROM user_settings
                WHERE username = ?
            """,
            (user["username"],)
        ).fetchone()
    if current_location_displayed:
        current_location_displayed = current_location_displayed[0]
    else:
        current_location_displayed = None
    current_skills_displayed_str = ""
    with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection:
        current_skills_displayed = connection.execute(
            """
                SELECT skill
                FROM skills
                WHERE username = ?
            """,
            (user["username"],)
        ).fetchall()
    if current_skills_displayed:
        for x in range(len(current_skills_displayed)):
            current_skills_displayed_str += current_skills_displayed[x][0] + "\n" #TODO Make each skill a new line

    else:
        current_skills_displayed_str = ""
    return render_template(
        "settings.html",
        user=user,
        current_email_displayed=current_email_displayed,
        current_pronouns_displayed=current_pronouns_displayed,
        current_bio_displayed=current_bio_displayed,
        current_job_displayed=current_job_displayed,
        current_location_displayed=current_location_displayed,
        current_skills_displayed_str=current_skills_displayed_str
    )
#current_pronouns_displayed=current_pronouns_displayed

@app.route("/change_wallpaper", methods=["POST"]) #TODO Remember this could bug on an old account if it's not in user settings.
def change_wallpaper():
    user = session.get("user")

    if not user:
        return redirect("/")

    file = request.files.get("picture")
    choice = request.form.get("choice")
    # Upload takes priority over the radio buttons
    if file and file.filename:
        try:
            image = Image.open(file.stream)
            image = ImageOps.fit(image, (1920, 1080))
            image = image.convert("RGB")

            image_bytes = io.BytesIO()
            image.save(image_bytes, format="JPEG")
            wallpaper_img = image_bytes.getvalue()

        except (UnidentifiedImageError, OSError):
            return render_template(
                "settings.html",
                user=user,
                message="Invalid image file."
            )
        wallpaper_setting = "custom"

    else:
    # Only validate the radio choice if no file was uploaded
        if choice not in ("dark", "light"):
            return render_template(
                "settings.html",
                user=user,
                message="Please select Dark or Light, or upload an image."
            )
        wallpaper_setting = choice
        wallpaper_img = None

    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        connection.execute(
            """
            UPDATE user_settings
            SET wallpaper_setting = ?, wallpaper_img = ?
            WHERE username = ?
            """,
            (wallpaper_setting, wallpaper_img, user["username"])
        )

    return redirect("/settings")

@app.route("/wallpaper/<username>")
def get_wallpaper_picture(username):
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "user_settings.db")
    )
    cursor = connection.cursor()

    cursor.execute(
        "SELECT wallpaper_setting, wallpaper_img FROM user_settings WHERE username = ?",
        (username,)
    )
    result = cursor.fetchone()
    connection.close()

    if not result:
        return "Wallpaper not found", 404

    wallpaper_setting = result[0]
    wallpaper_img = result[1]
    
    if wallpaper_setting == "custom":
        if not wallpaper_img:
            return "Custom wallpaper image not found", 404

        return wallpaper_img, 200, {"Content-Type": "image/jpeg"}

    return "Custom wallpaper is not selected", 404

@app.route("/add_public_email", methods=["POST"])
def add_public_email():
    user = session.get("user")
    
    if not user:
        return redirect("/")
    inputted_email = request.form.get("public_email", "").strip()
    if not len(inputted_email) <= 35:
        email_error = "Sorry, email must be 35 characters or less"
        return render_template("settings.html", user=user, email_error=email_error)
    if not inputted_email:
        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            connection.execute(
                """
                UPDATE user_settings
                SET public_email = ?
                WHERE username = ?
                """,
                ("", user["username"])
            )
        connection.commit()
        connection.close()
        return redirect("/settings")
    for char_email in range(len(inputted_email)):
        if inputted_email[char_email] == " ":
            email_error = "Email must have no spaces"
            return render_template("settings.html", user=user, email_error=email_error)
    email_endings = [
        "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "live.com", "msn.com", "aol.com", 
        "proton.me", 'protonmail.com', 'zoho.com', 'mail.com', 'gmx.com', "gmx.net", "yandex.com", "yandex.ru", 
        "hey.com", "fastmail.com", "tutanota.com", 'tuta.com', 'me.com', 'mac.com', 'googlemail.com'
    ] # all main email endings in str form
    list_of_email_endings_check = []
    for email_ending in email_endings:
        list_of_email_endings_check.append(inputted_email.endswith(f"{email_ending}"))

    for email_ending_check in list_of_email_endings_check:
        if email_ending_check == True:
            with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
                connection.execute(
                    """
                    UPDATE user_settings
                    SET public_email = ?
                    WHERE username = ?
                    """,
                    (inputted_email, user["username"])
                )
            connection.commit()
            connection.close()
            return redirect("/settings")
    email_error = "Invalid or unrecognizable email"
    return render_template("settings.html", user=user, email_error=email_error)

@app.route("/add_pronouns", methods=["POST"])
def add_pronouns():
    user = session.get("user")
    slash_count = 0
    if not user:
        return redirect("/")
    inputted_pronouns = request.form.get("pronouns", "").strip()
    if len(inputted_pronouns) >= 15:
        pronouns_error = "Sorry, pronouns must be under 15 characters"
        return render_template("settings.html", user=user, pronouns_error=pronouns_error)
    if not inputted_pronouns:
        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            connection.execute(
                """
                    UPDATE user_settings
                    SET pronouns = ?
                    WHERE username = ?
                """,
                ("", user["username"])
            )
        return redirect("/settings")
    for char_pronouns in range(len(inputted_pronouns)):
        if inputted_pronouns[char_pronouns] == "/":
            slash_count += 1
        elif inputted_pronouns[char_pronouns] == " ":
            pronouns_error = "Pronouns must have no spaces."
            return render_template("settings.html", user=user, pronouns_error=pronouns_error)
    if slash_count < 1:
        pronouns_error = "Pronouns must have a slash."
        return render_template("settings.html", user=user, pronouns_error=pronouns_error)
    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        connection.execute(
            """
                UPDATE user_settings
                SET pronouns = ?
                WHERE username = ?
            """,
            (inputted_pronouns, user["username"])
        )
    return redirect("/settings")

@app.route("/add_bio", methods=["POST"])
def add_bio():
    user = session.get("user")
    if not user:
        return redirect("/")
    inputted_bio = request.form.get("bio")
    if not inputted_bio:
        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            connection.execute(
                """
                    UPDATE user_settings
                    SET bio = ?
                    WHERE username = ?
                """,
                ("", user["username"])
            )
        return redirect("/settings")
    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        connection.execute(
            """
                UPDATE user_settings
                SET bio = ?
                WHERE username = ?
            """,
            (inputted_bio, user["username"])
        )
    return redirect("/settings")

@app.route("/add_job", methods=["POST"])
def add_job():
    user = session.get("user")
    if not user:
        return redirect("/")
    inputted_job = request.form.get("job")
    if not inputted_job:
        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            connection.execute(
                """
                    UPDATE user_settings
                    SET job = ?
                    WHERE username = ?
                """,
                ("", user["username"]) # on settings and profile this should be unemployed.
            )
        return redirect("/settings")
    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        connection.execute(
            """
                UPDATE user_settings
                SET job = ?
                WHERE username = ?
            """,
            (inputted_job, user["username"])
        )
    return redirect("/settings")

@app.route("/add_location", methods=["POST"])
def add_location():
    user = session.get("user")
    if not user:
        return redirect("/")
    inputted_location = request.form.get("location")
    if not inputted_location:
        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            connection.execute(
                """
                    UPDATE user_settings
                    SET location = ?
                    WHERE username = ?
                """,
                ("", user["username"])
            )
        return redirect("/settings")
    for char in range(len(inputted_location)):
        if not ((ord(inputted_location[char]) >= ord("a") and ord(inputted_location[char]) <= ord("z"))
        or 
        (ord(inputted_location[char]) >= ord("A") and ord(inputted_location[char]) <= ord("Z"))
        or
        inputted_location[char] == " "):
            location_error = "Inputted location must contain English characters only"
            return render_template("settings.html", user=user, location_error=location_error)
    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        connection.execute(
            """
                UPDATE user_settings
                SET location = ?
                WHERE username = ?
            """,
            (inputted_location, user["username"])
        )
    return redirect("/settings")

@app.route("/profile", methods=["POST"])
def profile_page_check():
    user = session.get("user")
    selected_user = request.form.get("selected_profile_user")
    select_user_setting = [] # list to hold each setting output. 
    if user and selected_user:
        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            current_items_in_user_settings = [
                "wallpaper_img",
                "wallpaper_setting",
                "public_email",
                "pronouns",
                "bio",
                "job",
                "location",
                "account_creation_day"
            ] # list of all items in user_settings. I made this so we can loop through the items.
            for num in range(len(current_items_in_user_settings)):
                select_user_setting.append(connection.execute( # maybe switch to append to remove error odds. 
                    f"""
                        SELECT {current_items_in_user_settings[num]}
                        FROM user_settings
                        WHERE username = ?
                    """,
                    (selected_user,)
                ).fetchone())
                if not select_user_setting[num]:
                    # if this sector is empty. 
                    select_user_setting[num] = "empty"
                    # we use empty as a placeholder rather than just "" to remove any potential confusion.
                else:
                    select_user_setting[num] = select_user_setting[num][0] 
        #DONE user_information where you a jumble of checks to see if a certain SELECT works maybe like we replace up top with a select loop where we select each item once and check if it exists via looping.
        with sqlite3.connect(os.path.join(currentdirectory, "friends.db")) as connection_friends:
                connection_friends.row_factory = sqlite3.Row
                friends = connection_friends.execute(
                    "SELECT * FROM friends WHERE receiver = ? OR username = ?",
                    (selected_user, selected_user)
                ).fetchall()
        names = []
        for friend in friends:
            if friend["username"] == selected_user and friend["receiver"]:
                names.append(friend["receiver"])
            elif friend["receiver"] == selected_user and friend["username"]:
                names.append(friend["username"])    # This will turn the whole jumble dict into a bunch of names.
        friend_count = len(set(names)) # just encase of a duplicate
        exist = friend_count > 0
        current_skills = []
        with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection_skills:
            connection_skills.row_factory = sqlite3.Row

            current_skills = connection_skills.execute(
                """
                SELECT skill, total_holes_dug
                FROM skills
                WHERE username = ?
                ORDER BY total_holes_dug DESC
                """,
                (selected_user,)
            ).fetchall()
        with sqlite3.connect(os.path.join(currentdirectory, "tasks_completed_today.db")) as connection_friends:
            connection_friends.row_factory = sqlite3.Row
            tasks_complete_today = connection_friends.execute(
                "SELECT * FROM tasks_completed_today WHERE username = ?",
                (selected_user,)
            ).fetchall()
        with sqlite3.connect(os.path.join(currentdirectory, "user_holes.db")) as connection_holes_dug:
            connection_holes_dug.row_factory = sqlite3.Row
            total_holes_dug = connection_holes_dug.execute(
                "SELECT total_holes_dug FROM user_holes WHERE username = ?",
                (selected_user,)
            ).fetchone()
        if total_holes_dug:
            total_holes_dug = total_holes_dug["total_holes_dug"]
        else:
            total_holes_dug = 0

        achievements = []
        with sqlite3.connect(os.path.join(currentdirectory, "achievements.db")) as connection_achievements:
            connection_achievements.row_factory = sqlite3.Row
            achievements_current = connection_achievements.execute(
                "SELECT achievement FROM achievements WHERE username = ?",
                (selected_user,)
            ).fetchall()
        for x in range(len(achievements_current)):
            achievements.append(achievements_current[x][0])
        return render_template(
            "profile_page.html",
            user=user,
            selected_user=selected_user,
            select_user_setting=select_user_setting,
            names=names,
            friend_count=friend_count,
            exist=exist,
            current_skills=current_skills,
            tasks_complete_today=tasks_complete_today,
            total_holes_dug=total_holes_dug,
            achievements=achievements
        )
    else:
        return redirect("/")

@app.route("/get_skills", methods=["GET", "POST"])
def get_skills_page():
    user = session.get("user")
    
    if not user:
        return redirect("/")
    text = request.values.get("input_search", "").strip().lower()
    skills = [] # final skills
    current_skills = [] # all skills already in the SQL
    with open(os.path.join(currentdirectory, "skills.txt"), "r", encoding="utf-8") as file:
        all_skills = [line.strip() for line in file if line.strip()]
    # every skill avaliable. All must start with a capitol letter at the beginning
    # Something related to this, all_skills = []
    with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection_skills:
        connection_skills.row_factory = sqlite3.Row
        skills_owned = connection_skills.execute(
            "SELECT skill FROM skills WHERE username = ?",
            (user["username"],)
        ).fetchall()

    for x in range(len(skills_owned)):
        current_skills.append(skills_owned[x][0])
    if text:
        for skill in all_skills:
            if skill.lower().startswith(text): # must start with the search and not be in previously added
                skills.append(skill)
    return render_template(
        "add_skills.html",
        username=user["username"],
        skills=skills,
        skills_input_search=text,
        current_skills=current_skills
    )

@app.route("/add_skills", methods=["POST"])
def add_skills():
    user = session.get("user")
    if not user:
        return redirect("/")

    selected_skill = request.form.get("skill")

    with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection:
        connection.execute(
            "INSERT INTO skills VALUES (?, ?, ?)",
            (user["username"], selected_skill, 0)
        )
    return redirect("/get_skills")

@app.route("/remove_skills", methods=["POST"])
def remove_skills():
    user = session.get("user")
    if not user:
        return redirect("/")

    remove_input = request.form.get("input_remove")
    skill = request.form.get("skill")
    if remove_input != "REMOVE":
        error_remove_message = 'Please input "REMOVE".'
        return render_template(
            "add_skills.html",
            username=user["username"],
            error_remove_message=error_remove_message
        )
    with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection:
        connection.execute(
            "DELETE FROM skills WHERE username = ? AND skill = ?",
            (user["username"], skill)
        )
    return redirect("/get_skills")

@app.route("/home_page", methods=["GET"])
def home_page():
    user = session.get("user")

    if not user:
        return redirect("/")
    daily_tasks = []
    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        result = connection.execute(
            "SELECT timezone FROM user_settings WHERE username = ?",
            (user["username"],)
        ).fetchone()

    timezone = result[0] if result and result[0] else "UTC"
    current_time = datetime.now(ZoneInfo(timezone))

    current_day = current_time.strftime("%A").lower()
    day_of_month = current_time.day
    current_date = current_time.date().isoformat()

    current_month = current_time.month
    current_year = current_time.year

    days_in_month = calendar.monthrange(current_year, current_month)[1] # use of calendar to get days in month
    current_skills = []
    with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection_skills:
        connection_skills.row_factory = sqlite3.Row
        skills_owned = connection_skills.execute(
            "SELECT skill FROM skills WHERE username = ?",
            (user["username"],)
        ).fetchall()
    for x in range(len(skills_owned)):
        current_skills.append(skills_owned[x][0])

    with sqlite3.connect(os.path.join(currentdirectory, "tasks_today.db")) as connection_tasks_today:
        connection_tasks_today.row_factory = sqlite3.Row
        connection_tasks_today.execute(
            "DELETE FROM tasks_today WHERE username = ?",
            (user["username"],)
        )
    
    with sqlite3.connect(os.path.join(currentdirectory, "tasks_reloader.db")) as connection_skills:
        connection_skills.row_factory = sqlite3.Row
        task_reloading = connection_skills.execute(
            "SELECT task, skill, recurrence, every_month_day FROM tasks_reloader WHERE username = ?",
            (user["username"],)
        ).fetchall()

    with sqlite3.connect(os.path.join(currentdirectory, "global_holes.db")) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT total_global_holes FROM global_holes",
        )
        global_holes_dug = cursor.fetchone()
        global_holes_dug = global_holes_dug[0] if global_holes_dug else 0

    for x in task_reloading:
        if x["recurrence"] == "every_day":
            connection = sqlite3.connect(
                os.path.join(currentdirectory, "tasks_today.db")
            )
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO tasks_today VALUES (?, ?, ?, ?)",
                (user["username"], x["task"], x["skill"], day_of_month)
            )
            # Recurrence is weekday it was created or like every day or month
            connection.commit()
            connection.close()
        elif "every_" + current_day == x["recurrence"]:
            connection = sqlite3.connect(
                os.path.join(currentdirectory, "tasks_today.db")
            )
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO tasks_today VALUES (?, ?, ?, ?)",
                (user["username"], x["task"], x["skill"], day_of_month)
            )
            connection.commit()
            connection.close()
        elif x["recurrence"] == "every_month":
            try:
                monthly_day = int(x["every_month_day"])
            except (TypeError, ValueError):
                continue

            if monthly_day == day_of_month or (
                monthly_day > days_in_month
                and day_of_month == days_in_month
            ):
                connection = sqlite3.connect(
                    os.path.join(currentdirectory, "tasks_today.db")
                )
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO tasks_today (username, task, skill, day_of_month_added)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user["username"], x["task"], x["skill"], day_of_month)
                )
                connection.commit()
                connection.close()

    # This query must be OUTSIDE the loop.
    with sqlite3.connect(os.path.join(currentdirectory, "tasks_today.db")) as connection_tasks_today:
        connection_tasks_today.row_factory = sqlite3.Row

        connection_tasks_today.execute(
            "ATTACH DATABASE ? AS completed_db",
            (os.path.join(currentdirectory, "tasks_completed_today.db"),)
        )

        current_tasks = connection_tasks_today.execute(
            """
            SELECT *
            FROM tasks_today
            WHERE username = ?
            AND task NOT IN (
                SELECT task
                FROM completed_db.tasks_completed_today
                WHERE username = ?
                AND day_of_month_completed = ?
            )
            """,
            (user["username"], user["username"], current_date)
        ).fetchall()

    return render_template(
        "home_page.html",
        user=user,
        current_skills=current_skills,
        current_tasks=current_tasks,
        global_holes_dug=global_holes_dug
    )
        
@app.route("/add_task", methods=["POST"])
def add_task():
    user = session.get("user")

    if not user:
        return redirect("/")

    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        result = connection.execute(
            "SELECT timezone FROM user_settings WHERE username = ?",
            (user["username"],)
        ).fetchone()

    timezone = result[0] if result and result[0] else "UTC"
    current_time = datetime.now(ZoneInfo(timezone))

    current_day = current_time.strftime("%A").lower()
    day_of_month = current_time.day
    current_date = current_time.date().isoformat()

    task_input = request.form.get("task_input", "").strip()
    selected_skill = request.form.get("skills_radio")
    selected_habit = request.form.get("habitual_radio")

    if not task_input:
        error_message = "Please input the task you want to add."
    elif not selected_skill:
        error_message = "Please select a skill."
    elif not selected_habit:
        error_message = "Please select a recurrence."
    else:
        error_message = None

    if error_message:
        with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection:
            current_skills = connection.execute(
                "SELECT skill FROM skills WHERE username = ?",
                (user["username"],)
            ).fetchall()
        current_skills = [skill[0] for skill in current_skills]

        with sqlite3.connect(os.path.join(currentdirectory, "tasks_today.db")) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute(
                "ATTACH DATABASE ? AS completed_db",
                (os.path.join(currentdirectory, "tasks_completed_today.db"),)
            )
            

            current_tasks = connection.execute(
                """
                SELECT *
                FROM tasks_today
                WHERE username = ?
                AND task NOT IN (
                    SELECT task
                    FROM completed_db.tasks_completed_today
                    WHERE username = ?
                    AND day_of_month_completed = ?
                )
                """,
                (user["username"], user["username"], current_date)
            ).fetchall()

        return render_template(
            "home_page.html",
            user=user,
            current_skills=current_skills,
            current_tasks=current_tasks,
            error_message=error_message
        )
    with sqlite3.connect(os.path.join(currentdirectory, "tasks_reloader.db")) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM tasks_reloader WHERE username = ?",
            (user["username"],)
        )

        tasks = cursor.fetchall()
    if len(tasks) >= 75:
        error_message = "Over 75 scheduled tasks! Please remove a task to add this task."

        # Load the skills again for home_page.html
        with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection:
            current_skills = connection.execute(
                "SELECT skill FROM skills WHERE username = ?",
                (user["username"],)
            ).fetchall()
        current_skills = [skill[0] for skill in current_skills]

        # Load the tasks again for home_page.html
        with sqlite3.connect(os.path.join(currentdirectory, "tasks_today.db")) as connection:
            connection.row_factory = sqlite3.Row
            current_tasks = connection.execute(
                "SELECT * FROM tasks_today WHERE username = ?",
                (user["username"],)
            ).fetchall()

        return render_template(
            "home_page.html",
            user=user,
            current_skills=current_skills,
            current_tasks=current_tasks,
            error_message=error_message
        )
    with sqlite3.connect(os.path.join(currentdirectory, "tasks_reloader.db")) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT task FROM tasks_reloader WHERE username = ?",
            (user["username"],)
        )
        task = cursor.fetchall()

    for x in task:
        if x[0].strip().lower() == task_input.lower():
            error_message = "Task has already been created!"

            with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection:
                current_skills = connection.execute(
                    "SELECT skill FROM skills WHERE username = ?",
                    (user["username"],)
                ).fetchall()
            current_skills = [skill[0] for skill in current_skills]

            with sqlite3.connect(os.path.join(currentdirectory, "tasks_today.db")) as connection:
                connection.row_factory = sqlite3.Row
                current_tasks = connection.execute(
                    "SELECT * FROM tasks_today WHERE username = ?",
                    (user["username"],)
                ).fetchall()

            return render_template(
                "home_page.html",
                user=user,
                current_skills=current_skills,
                current_tasks=current_tasks,
                error_message=error_message
            )
    connection = sqlite3.connect(
        os.path.join(currentdirectory, "tasks_reloader.db")
    )
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO tasks_reloader VALUES (?, ?, ?, ?, ?)",
        (user["username"], task_input, selected_skill, selected_habit, day_of_month)
    )
    connection.commit()
    connection.close()

    return redirect("/home_page")

@app.route("/complete_task", methods=["POST"])
def complete_task():
    user = session.get("user")
    
    if not user:
        return redirect("/")
    
    with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
        result = connection.execute(
            "SELECT timezone FROM user_settings WHERE username = ?",
            (user["username"],)
        ).fetchone()

    timezone = result[0] if result and result[0] else "UTC"
    current_time = datetime.now(ZoneInfo(timezone))

    current_day = current_time.strftime("%A").lower()
    day_of_month = current_time.day
    current_date = current_time.date().isoformat()

    selected_skill_completed = request.form.get("selected_skill_completed")
    selected_task_completed = request.form.get("selected_task_completed")
    if not selected_task_completed or not selected_skill_completed:
        return redirect("/home_page")

    with sqlite3.connect(os.path.join(currentdirectory, "tasks_completed_today.db")) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE  FROM tasks_completed_today WHERE username = ? AND day_of_month_completed != ?",
            (user["username"], current_date)
        )
    
    with sqlite3.connect(os.path.join(currentdirectory, "tasks_completed_today.db")) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO tasks_completed_today VALUES(?, ?, ?, ?)",
            (user["username"], selected_task_completed, selected_skill_completed, current_date)
        )
    with sqlite3.connect(os.path.join(currentdirectory, "tasks_today.db")) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE  FROM tasks_today WHERE username = ? AND task = ?",
            (user["username"], selected_task_completed)
        )

    with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE skills
            SET total_holes_dug = total_holes_dug + 1
            WHERE username = ? AND skill = ?;
            """,
            (user["username"], selected_skill_completed)
        )
    with sqlite3.connect(os.path.join(currentdirectory, "user_holes.db")) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE user_holes
            SET total_holes_dug = total_holes_dug + 1
            WHERE username = ?
            """,
            (user["username"],)
        )
    with sqlite3.connect(os.path.join(currentdirectory, "global_holes.db")) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE global_holes
                SET total_global_holes  = total_global_holes  + 1
                """
            )
        
    return redirect("/home_page")

@app.route("/delete_task", methods=["POST"])
def delete_task():
    user = session.get("user")

    if not user:
        return redirect("/")

    selected_task_deleted = request.form.get("selected_task_deleted", "").strip()

    if not selected_task_deleted:
        return redirect("/home_page")

    with sqlite3.connect(
        os.path.join(currentdirectory, "tasks_reloader.db")
    ) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            DELETE FROM tasks_reloader
            WHERE username = ? AND task = ?
            """,
            (user["username"], selected_task_deleted)
        )

    return redirect("/home_page")

@app.route("/load_add_achievements", methods=["GET"])
def load_add_achievements():
    user = session.get("user")
    
    if not user:
        return redirect("/")

    achievements = []
    with sqlite3.connect(os.path.join(currentdirectory, "achievements.db")) as connection_achievements:
        connection_achievements.row_factory = sqlite3.Row
        achievements_current = connection_achievements.execute(
            "SELECT achievement FROM achievements WHERE username = ?",
            (user["username"],)
        ).fetchall()
    for x in range(len(achievements_current)):
        achievements.append(achievements_current[x][0])
    
    
    return render_template("add_achievements.html", achievements=achievements)

@app.route("/add_achievement", methods=["POST"])
def add_achievement():
    user = session.get("user")
        
    if not user:
        return redirect("/")
    
    achievement_input = request.form.get("achievement_input", "").strip()

    if not achievement_input:
        return redirect("/load_add_achievements")
    
    with sqlite3.connect(os.path.join(currentdirectory, "achievements.db")) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT achievement FROM achievements WHERE username = ?",
            (user["username"],)
        )

        achievements = cursor.fetchall()
    if len(achievements) >= 30:
        error_message = "Over 30 achievements! Please remove an achievement to add this achievement."
        
        # Load the achievements again for add_achievements.html
        with sqlite3.connect(os.path.join(currentdirectory, "achievements.db")) as connection:
            current_achievements = connection.execute(
                "SELECT achievement FROM achievements WHERE username = ?",
                (user["username"],)
            ).fetchall() 
        current_achievements = [current_achievement[0] for current_achievement in current_achievements]
        return render_template(
            "add_achievements.html",
            user=user,
            achievements=current_achievements,
            error_message=error_message
        )
    cursor.execute(
        "SELECT achievement FROM achievements WHERE username = ?",
        (user["username"],)
    )

    achievements = cursor.fetchall()

    for x in achievements:
        if x[0].strip().lower() == achievement_input.strip().lower():
            error_message = "Achievement has already been created!"

            with sqlite3.connect(os.path.join(currentdirectory, "achievements.db")) as connection:
                current_achievements = connection.execute(
                    "SELECT achievement FROM achievements WHERE username = ?",
                    (user["username"],)
                ).fetchall()

            current_achievements = [
                current_achievement[0]
                for current_achievement in current_achievements
            ]

            return render_template(
                "add_achievements.html",
                user=user,
                achievements=current_achievements,
                error_message=error_message
            )
    with sqlite3.connect(os.path.join(currentdirectory, "achievements.db")) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO achievements VALUES (?, ?)",
            (user["username"], achievement_input)
        )
    return redirect("/load_add_achievements")
    
@app.route("/remove_achievement", methods=["POST"])
def remove_achievement():
    user = session.get("user")
            
    if not user:
        return redirect("/")

    selected_achievement_deleted = request.form.get("selected_achievement_deleted")

    if not selected_achievement_deleted:
        return redirect("/load_add_achievements")

    with sqlite3.connect(os.path.join(currentdirectory, "achievements.db")) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM achievements WHERE username = ? AND achievement = ?",
            (user["username"], selected_achievement_deleted)
        )
    
    return redirect("/load_add_achievements")

@app.route("/DELETE_ACCOUNT", methods=["POST"]) # All caps because VERY important to not mess up. 
def DELETE_ACCOUNT():
    user = session.get("user")

    if not user:
        return redirect("/")

    input_remove_account = request.form.get("input_remove_account")
    username = user["username"]

    if not input_remove_account == "REMOVE":
        error_message_remove = 'You must input "REMOVE" to remove your account.'
        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            current_email_displayed = connection.execute(
                """
                    SELECT public_email
                    FROM user_settings
                    WHERE username = ?
                """,
                (user["username"],)
            ).fetchone()
        if current_email_displayed:
            current_email_displayed = current_email_displayed[0]
        else:
            current_email_displayed = None

        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            current_pronouns_displayed = connection.execute(
                """
                    SELECT pronouns
                    FROM user_settings
                    WHERE username = ?
                """,
                (user["username"],)
            ).fetchone()
        if current_pronouns_displayed:
            current_pronouns_displayed = current_pronouns_displayed[0]
        else:
            current_pronouns_displayed = None
        
        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            current_bio_displayed = connection.execute(
                """
                    SELECT bio
                    FROM user_settings
                    WHERE username = ?
                """,
                (user["username"],)
            ).fetchone()
        if current_bio_displayed:
            current_bio_displayed = current_bio_displayed[0]
        else:
            current_bio_displayed = None
        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
                current_job_displayed = connection.execute(
                    """
                        SELECT job
                        FROM user_settings
                        WHERE username = ?
                    """,
                    (user["username"],)
                ).fetchone()
        if current_job_displayed:
            current_job_displayed = current_job_displayed[0]
        else:
            current_job_displayed = None
        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            current_location_displayed = connection.execute(
                """
                    SELECT location
                    FROM user_settings
                    WHERE username = ?
                """,
                (user["username"],)
            ).fetchone()
        if current_location_displayed:
            current_location_displayed = current_location_displayed[0]
        else:
            current_location_displayed = None
        current_skills_displayed_str = ""
        with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection:
            current_skills_displayed = connection.execute(
                """
                    SELECT skill
                    FROM skills
                    WHERE username = ?
                """,
                (user["username"],)
            ).fetchall()
        if current_skills_displayed:
            for x in range(len(current_skills_displayed)):
                current_skills_displayed_str += current_skills_displayed[x][0] + "\n" #TODO Make each skill a new line

        else:
            current_skills_displayed_str = ""
        return render_template(
            "settings.html",
            user=user,
            current_email_displayed=current_email_displayed,
            current_pronouns_displayed=current_pronouns_displayed,
            current_bio_displayed=current_bio_displayed,
            current_job_displayed=current_job_displayed,
            current_location_displayed=current_location_displayed,
            current_skills_displayed_str=current_skills_displayed_str,
            error_message_remove=error_message_remove
        )
    else:
        # Delete the user's profile
        with sqlite3.connect(os.path.join(currentdirectory, "profile.db")) as connection:
            connection.execute(
                "DELETE FROM profile WHERE username = ?",
                (username,)
            )

        # Delete the user's settings
        with sqlite3.connect(os.path.join(currentdirectory, "user_settings.db")) as connection:
            connection.execute(
                "DELETE FROM user_settings WHERE username = ?",
                (username,)
            )

        # Delete friend requests sent or received by the user
        with sqlite3.connect(os.path.join(currentdirectory, "requests.db")) as connection:
            connection.execute(
                "DELETE FROM requests WHERE sender = ? OR receiver = ?",
                (username, username)
            )

        # Delete friendships involving the user
        with sqlite3.connect(os.path.join(currentdirectory, "friends.db")) as connection:
            connection.execute(
                "DELETE FROM friends WHERE username = ? OR receiver = ?",
                (username, username)
            )

        # Delete user based holes involving the user
        with sqlite3.connect(os.path.join(currentdirectory, "user_holes.db")) as connection:
            connection.execute(
                "DELETE FROM user_holes WHERE username = ?",
                (username,)
            )
        # Delete skills involving the user
        with sqlite3.connect(os.path.join(currentdirectory, "skills.db")) as connection:
            connection.execute(
                "DELETE FROM skills WHERE username = ?",
                (username,)
            )
        # Delete tasks_completed_today involving the user
        with sqlite3.connect(os.path.join(currentdirectory, "tasks_completed_today.db")) as connection:
            connection.execute(
                "DELETE FROM tasks_completed_today WHERE username = ?",
                (username,)
            )
        # Delete tasks_reloader involving the user
        with sqlite3.connect(os.path.join(currentdirectory, "tasks_reloader.db")) as connection:
            connection.execute(
                "DELETE FROM tasks_reloader WHERE username = ?",
                (username,)
            )
        # Delete tasks_today involving the user
        with sqlite3.connect(os.path.join(currentdirectory, "tasks_today.db")) as connection:
            connection.execute(
                "DELETE FROM tasks_today WHERE username = ?",
                (username,)
            )
        # Delete achievements involving the user
        with sqlite3.connect(os.path.join(currentdirectory, "achievements.db")) as connection:
            connection.execute(
                "DELETE FROM achievements WHERE username = ?",
                (username,)
            )
        session.clear()
        return redirect("/")
# Keep this at the bottom. This is what starts the server.
if __name__ == "__main__":
    app.run(debug=True)

#DONE FINISHED 10/20/26 with 15 hours done today! I need to fix the background bug where when I select custom it just like shows white and also when I make the mode dark the main text is light no matter?
#DONE Make sure you yourself don't appear on the friend request page
#DONE Make the text change colors on like the settings page, for some reason that is bugged.
#DONE add bio and stuff
#DONE add individual profiles
# DONE Add profile on friend list
# DONE Add unfriend option.
# DONE On profile page add the skills ranked by holes dug for each one on the side segment. 
# DONE Daily activities are the history of the activities done in that day laid out like people search
# DONE Holes dug overall on the profile
# DONE Add the task adder on homepage. HARDEST SEGMENT PROBABLY. 