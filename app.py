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

from flask import Flask, render_template, make_response, redirect, request, session, url_for

from PIL import Image, ImageOps, UnidentifiedImageError
# Pillow is a sort of extension to help us tweak the images. Had to use AI on finding out this one, sadly.

import io


# This dude gives us space to hold what we want in an SQL table like an image and compress it.

from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

currentdirectory = os.path.dirname(os.path.abspath(__file__))


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

currentdirectory = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder="frontend", static_url_path="")
app.secret_key = "blahblahblah"

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
        return render_template("home_page.html", user=user)

    return render_template("front_page.html")

@app.route("/sign_up", methods=["POST"])
def sign_up():
    username = request.form["username"]
    password = request.form["password"]
    confirm_password = request.form["confirm_password"]
    message = "" # message is blank every rerun?
    # Checks if username is null or password.
    default_image = Image.open(
        os.path.join(currentdirectory, "static", "placeholder.png")
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
            location TEXT
        )
    """) #IMPORTANT 8 Elements in here currently
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
        connection = sqlite3.connect(
            os.path.join(currentdirectory, "user_settings.db")
        )
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO user_settings VALUES (?, ?, ?, ?, ? ,?, ?, ?)",
            (username, "", "dark", "", "", "", "", "") 
            # dark is the background setting and username is the user and the "" is the image we are working with, the other stuff are "" because it is blank when first initialized
        )
        connection.commit()
        connection.close()
        connection, cursor = get_connection_for_profile()
        # Username doesn't exist
        # Cursor is what you use to send commands to the database
        hashed_password = generate_password_hash(password)
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

@app.route("/home_page", methods=["GET"])
def home_page():
    user = session.get("user")

    if not user:
        return redirect("/")

    return render_template("home_page.html", user=user)

# Zis is the homepage clearly. TODO

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
    connection.close() #SUS TODO
    # 0 here just gets the value rather than key and value.
    return profile_picture, 200, {"Content-Type": "image/jpeg"}
    # 200 is the value that means that everything worked out and third item tells flask what kind of item we are sending and the browser read and decodes it. 

@app.route("/profile")
def profile_page_check(): #This whole thing needs to go by user. Not just as a blatant /profile.
    user = session.get("user")
    if user:
        return render_template("profile_page.html", user=user)
    else:
        return render_template("front_page.html")

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
        # TODO
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
    connection.commit()
    connection.close()
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
    exist = len(names) > 0
    return render_template("friends_list.html", user=user, names=names, exist=exist)

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
    return render_template(
        "settings.html",
        user=user,
        current_email_displayed=current_email_displayed,
        current_pronouns_displayed=current_pronouns_displayed
    )
#current_pronouns_displayed=current_pronouns_displayed

@app.route("/change_wallpaper", methods=["POST"]) #TODO Remeber this could bug on an old account if it's not in user settings.
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
        connection.commit()
        connection.close()
        return redirect("/settings")
    for char_pronouns in range(len(inputted_pronouns)):
        if inputted_pronouns[char_pronouns] == "/":
            slash_count += 1
        elif inputted_pronouns[char_pronouns] == " ":
            pronouns_error = "Pronouns must have no spaces"
            return render_template("settings.html", user=user, pronouns_error=pronouns_error)
    if slash_count < 1:
        pronouns_error = "Pronouns must have a slash"
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
    connection.commit()
    connection.close()
    return redirect("/settings")

# Keep this at the bottom. This is what starts the server.
if __name__ == "__main__":
    app.run(debug=True)

#TODO FINISHED 10/20/26 with 15 hours done today! I need to fix the background bug where when I select custom it just like shows white and also when I make the mode dark the main text is light no matter?
#DONE Make sure you yourself don't appear on the friend request page
#TODO Make the text change colors on like the settings page, for some reason that is bugged.
#TODO add bio and stuff
#TODO add individual profiles
