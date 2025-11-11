from app import app, db, jsonify, jwt
from sqlalchemy import text
from flask import request
from werkzeug.security import check_password_hash
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity, get_jwt
)


@app.post('/login')
def login():
    form = request.get_json()
    if not form:
        return {"error": "No input data provided"}, 400
    if not form.get('user_name'):
        return {"error": "UserName is required"}, 400
    if not form.get('password'):
        return {"error": "Password is required"}, 400

    user_name = form.get('user_name')
    password = form.get('password')

    sql = text("""SELECT * FROM user WHERE user_name = :user_name""")
    result = db.session.execute(sql, {'user_name': user_name}).fetchone()
    if not result:
        return {"error": "Invalid username or password"}, 401

    user = dict(result._mapping)
    if not check_password_hash(user['password'], password):
        return {"error": "Invalid username or password"}, 401

    additional_claims = {
        "user_name": user['user_name'],
        "profile": user['profile']
    }
    access_token = create_access_token(
        identity=str(user['id']),
        additional_claims=additional_claims
    )
    return {
               "message": "Login successful",
               "access_token": access_token
           }, 200


@app.get("/me")
@jwt_required()
def me():
    user = get_jwt_identity()
    return jsonify(
        user=user,
        info=get_jwt()
    )


@app.post('/protected')
@jwt_required()
def get_protected():
    return {
               "data": "Protected data access granted",
           }, 200


REVOKED_JTIS = set()


@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_data):
    return jwt_data["jti"] in REVOKED_JTIS


@app.post("/logout")
@jwt_required()  # revoke current access token
def logout():
    jti = get_jwt()["jti"]
    REVOKED_JTIS.add(jti)
    return jsonify(msg="Access token revoked")