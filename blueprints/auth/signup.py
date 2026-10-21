from . import bp
from flask import request, render_template, redirect, session
from PIL import Image, ImageOps
import io
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from db.conn import get_conn

@bp.route("/sign_up", methods=["POST"])
def sign_up():
    username = request.form["username"]
    password = request.form["password"]
    confirm_password = request.form["confirm_password"]
    message = "" # message is blank every rerun?
    # Checks if username is null or password.
    default_image = Image.open("static/placeholder.png")
    inputs = [username, password, confirm_password]

    default_image = ImageOps.fit(default_image, (500, 500)) # Centers and crops the image.

    default_image = default_image.convert("RGB")

    default_image_bytes = io.BytesIO()
    default_image.save(default_image_bytes, format="JPEG", quality=80)
    """
        These two lines look weird but the first var is just empty storage created by io. Now you save it to the default_image_bytes or the first parameter
        as a jpeg with a quality of 80.
    """
    
    encoded_image = default_image_bytes.getvalue()

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
    
    connection, cursor = get_conn()

    cursor.execute(
        "SELECT * FROM profile WHERE username = ?",
        (username,)
    )
    # gets the inputted username and has to have the comma because it's a tuple. 
    user = cursor.fetchone()
    # gets the first row that appears. You can also use these to do the sign up.
    if not user and password == confirm_password:
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

        # Give us the username as a session so it can remain logged in and can be used.

        return redirect("/home_page_check")
    elif password != confirm_password:
        message = "Please make sure that your confirmed password matches your password."
        password = ""
        confirm_password = ""
        return render_template(
            "sign_up_page.html",
            username=username,
            message=message
        )
    elif user:
        message = "Username already exists."
        username = ""
        return render_template(
            "sign_up_page.html",
            username=username,
            password=password,
            confirm_password=confirm_password,
            message=message
        )