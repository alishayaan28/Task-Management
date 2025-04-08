from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import google.oauth2.id_token
from google.auth.transport import requests
from google.cloud import firestore
from typing import Dict, Any
import os


# define the app that will contain all of our routing for Fast API 
app = FastAPI()

# firebase adapter
firebase_request_adapter = requests.Request()

# define the static and templates directories
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")

# Initialize Firestore client
db = firestore.Client()

# Main.html Route
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    id_token = request.cookies.get("token")
    error_message = None
    user_token = None
    user_boards = []

    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            if user_token:
                user_id = user_token['user_id']
                user_boards = await get_user_task_boards(user_id)
                
        except ValueError as err:
            print(str(err))
            user_token = None 
            error_message = str(err)

    return templates.TemplateResponse('main.html', {
        'request': request,
        'user_token': user_token,
        'error_message': error_message,
        'user_boards': user_boards
    })

# Route for logout
@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie(key="token")
    return response


# User functions
async def create_user(user_id: str, email: str, name: str = ""):
    user_ref = db.collection('users').document(user_id)
    user_data = {
        'email': email,
        'name': name,
        'created_at': firestore.SERVER_TIMESTAMP
    }
    user_ref.set(user_data)
    return user_data

async def get_user(user_id: str):
    user_ref = db.collection('users').document(user_id)
    user = user_ref.get()
    if user.exists:
        return user.to_dict()
    return None

# Task board functions
async def create_task_board(user_id: str, title: str, description: str = ""):
    board_ref = db.collection('task_boards').document()
    board_data = {
        'title': title,
        'description': description,
        'creator_id': user_id,
        'members': [user_id],
        'created_at': firestore.SERVER_TIMESTAMP
    }
    board_ref.set(board_data)
    return {"id": board_ref.id, **board_data}

async def get_task_board(board_id: str):
    board_ref = db.collection('task_boards').document(board_id)
    board = board_ref.get()
    if board.exists:
        return {"id": board_id, **board.to_dict()}
    return None

async def get_user_task_boards(user_id: str):
    # Get boards where user is a member
    boards_query = db.collection('task_boards').where('members', 'array_contains', user_id)
    boards = []
    for board in boards_query.stream():
        boards.append({"id": board.id, **board.to_dict()})
    return boards

# Task functions
async def create_task(board_id: str, title: str, description: str, creator_id: str, assigned_users: list = None):
    if assigned_users is None:
        assigned_users = []
        
    task_ref = db.collection('task_boards').document(board_id).collection('tasks').document()
    task_data = {
        'title': title,
        'description': description,
        'creator_id': creator_id,
        'assigned_users': assigned_users,
        'status': 'pending',
        'created_at': firestore.SERVER_TIMESTAMP
    }
    task_ref.set(task_data)
    return {"id": task_ref.id, **task_data}

async def get_task(board_id: str, task_id: str):
    task_ref = db.collection('task_boards').document(board_id).collection('tasks').document(task_id)
    task = task_ref.get()
    if task.exists:
        return {"id": task_id, **task.to_dict()}
    return None

async def get_board_tasks(board_id: str):
    tasks_query = db.collection('task_boards').document(board_id).collection('tasks')
    tasks = []
    for task in tasks_query.stream():
        tasks.append({"id": task.id, **task.to_dict()})
    return tasks

async def assign_user_to_task(board_id: str, task_id: str, user_id: str):
    task_ref = db.collection('task_boards').document(board_id).collection('tasks').document(task_id)
    task = task_ref.get()
    
    if task.exists:
        task_data = task.to_dict()
        assigned_users = task_data.get('assigned_users', [])
        
        if user_id not in assigned_users:
            assigned_users.append(user_id)
            task_ref.update({'assigned_users': assigned_users})
            
        return True
    return False


# Route for creating a new task board
@app.get("/create-board", response_class=HTMLResponse)
async def create_board_page(request: Request):
    id_token = request.cookies.get("token")
    user_token = None
    error_message = None

    if not id_token:
        return RedirectResponse(url="/")
    
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
    except ValueError as err:
        print(str(err))
        return RedirectResponse(url="/")

    return templates.TemplateResponse('create_board.html', {
        'request': request,
        'user_token': user_token,
        'error_message': error_message
    })

# Route for handling board creation
@app.post("/create-board")
async def create_board_submit(request: Request, title: str = Form(...), description: str = Form("")):
    id_token = request.cookies.get("token")
    
    if not id_token:
        return RedirectResponse(url="/")
    
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']
        board = await create_task_board(user_id, title, description)
        return RedirectResponse(url="/", status_code=303)
    except ValueError as err:
        print(str(err))
        return RedirectResponse(url="/")

# Routes for task board
@app.get("/board/{board_id}", response_class=HTMLResponse)

async def view_board(request: Request, board_id: str):

    id_token = request.cookies.get("token")

    error_message = None

    user_token = None

    board = None

    tasks = []

    if not id_token:

        return RedirectResponse(url="/")

    try:

        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)

        user_id = user_token['user_id']
        board = await get_task_board(board_id)

        if not board:

            return RedirectResponse(url="/")


        if user_id not in board.get('members', []):

            return RedirectResponse(url="/")

        tasks = await get_board_tasks(board_id)

    except ValueError as err:

        print(str(err))

        return RedirectResponse(url="/")

    return templates.TemplateResponse('board.html', {

        'request': request,

        'user_token': user_token,

        'error_message': error_message,

        'board': board,

        'tasks': tasks

    })