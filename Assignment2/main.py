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

                email = user_token.get('email', '')

                boards_query = db.collection('task_boards').where('members', 'array_contains', user_id)

                for board in boards_query.stream():

                    board_data = board.to_dict()

                    board_data['id'] = board.id

                    user_boards.append(board_data)

                temp_user_id = f"temp_{email.replace('@', '_at_').replace('.', '_dot_')}"
                boards_query_temp = db.collection('task_boards').where('members', 'array_contains', temp_user_id)

                for board in boards_query_temp.stream():

                    board_data = board.to_dict()
                    board_data['id'] = board.id

                    if not any(b['id'] == board.id for b in user_boards):

                        user_boards.append(board_data)

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
    boards_query = db.collection('task_boards').where('members', 'array_contains', user_id)
    boards = []
    for board in boards_query.stream():
        boards.append({"id": board.id, **board.to_dict()})
    return boards

# Task functions
async def create_task(
    board_id: str, 
    title: str, 
    description: str, 
    creator_id: str, 
    assigned_users: list = None,
    due_date: str = None
):
    if assigned_users is None:
        assigned_users = []
        
    task_ref = db.collection('task_boards').document(board_id).collection('tasks').document()
    task_data = {
        'title': title,
        'description': description,
        'creator_id': creator_id,
        'assigned_users': assigned_users,
        'status': 'pending',
        'created_at': firestore.SERVER_TIMESTAMP,
        'due_date': due_date,
        'completed_at': None
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
        email = user_token.get('email', '')
        temp_user_id = f"temp_{email.replace('@', '_at_').replace('.', '_dot_')}"
        
        board = await get_task_board(board_id)

        if not board:
            return RedirectResponse(url="/")

        # Check if either user's real ID or temp ID is in the members list
        if user_id not in board.get('members', []) and temp_user_id not in board.get('members', []):
            return RedirectResponse(url="/")

        # If user is accessing with temp ID, update board to use real ID
        if temp_user_id in board.get('members', []) and user_id not in board.get('members', []):
            board_ref = db.collection('task_boards').document(board_id)
            members = board.get('members', [])
            members.remove(temp_user_id)
            members.append(user_id)
            board_ref.update({'members': members})
            # Update the board data for the template
            board['members'] = members

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


# Routes for Add Member
@app.get("/board/{board_id}/add-member", response_class=HTMLResponse)

async def add_member_page(request: Request, board_id: str):

    id_token = request.cookies.get("token")

    error_message = None

    success_message = None

    user_token = None

    board = None

    members_info = []

    if not id_token:

        return RedirectResponse(url="/")

    try:

        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)

        user_id = user_token['user_id']

        board = await get_task_board(board_id)

        if not board:

            return RedirectResponse(url="/")

        if board.get('creator_id') != user_id:

            return RedirectResponse(url=f"/board/{board_id}")

        

        board_ref = db.collection('task_boards').document(board_id)

        board_data = board_ref.get().to_dict()

        member_emails = board_data.get('member_emails', {})

        

        for member_id in board.get('members', []):

            if member_id in member_emails:

                members_info.append({

                    'id': member_id,

                    'email': member_emails[member_id],

                    'is_creator': member_id == board.get('creator_id', '')

                })

                continue

                

            if member_id == user_id:

                members_info.append({

                    'id': member_id,

                    'email': user_token.get('email', 'Your account'),

                    'is_creator': member_id == board.get('creator_id', '')

                })

                

                if 'email' in user_token:

                    member_emails[member_id] = user_token['email']

                    board_ref.update({'member_emails': member_emails})

                continue

                

            if member_id.startswith('temp_'):

                email = member_id.replace('temp_', '').replace('_at_', '@').replace('_dot_', '.')

                members_info.append({

                    'id': member_id,

                    'email': email,

                    'is_creator': member_id == board.get('creator_id', '')

                })

                

                member_emails[member_id] = email

                board_ref.update({'member_emails': member_emails})

                continue

            

            members_info.append({

                'id': member_id,

                'email': f"User {member_id[:6]}...",

                'is_creator': member_id == board.get('creator_id', '')

            })

    except ValueError as err:

        print(str(err))

        return RedirectResponse(url="/")

    return templates.TemplateResponse('add_member.html', {

        'request': request,
        'user_token': user_token,
        'error_message': error_message,
        'success_message': success_message,
        'board': board,
        'members_info': members_info

    })

@app.post("/board/{board_id}/add-member")
async def add_member_submit(request: Request, board_id: str, email: str = Form(...)):
    id_token = request.cookies.get("token")

    if not id_token:
        return RedirectResponse(url="/")

    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']
        board = await get_task_board(board_id)

        if not board:
            return RedirectResponse(url="/")
        
        if board.get('creator_id') != user_id:
            return RedirectResponse(url=f"/board/{board_id}")
            
        users_ref = db.collection('users').where('email', '==', email)
        users = [doc for doc in users_ref.stream()]

        board_ref = db.collection('task_boards').document(board_id)
        board_data = board_ref.get().to_dict()
        member_emails = board_data.get('member_emails', {})

        if not users:
            temp_user_id = f"temp_{email.replace('@', '_at_').replace('.', '_dot_')}"
            user_data = {
                'email': email,
                'created_at': firestore.SERVER_TIMESTAMP,
                'temp_user': True
            }
            db.collection('users').document(temp_user_id).set(user_data)
            member_id = temp_user_id
            
            # Store email directly in the board
            member_emails[member_id] = email
            
            print(f"Created temporary user record for {email} with ID {temp_user_id}")
        else:
            member_id = users[0].id
            user_email = users[0].to_dict().get('email')
            
            # Store email directly in the board
            member_emails[member_id] = user_email

        if member_id in board.get('members', []):
            # Get members info for error message
            members_info = []
            for mid in board.get('members', []):
                if mid in member_emails:
                    members_info.append({
                        'id': mid,
                        'email': member_emails[mid],
                        'is_creator': mid == board.get('creator_id', '')
                    })
                elif mid == user_id:
                    members_info.append({
                        'id': mid,
                        'email': user_token.get('email', 'Your account'),
                        'is_creator': mid == board.get('creator_id', '')
                    })
                elif mid.startswith('temp_'):
                    temp_email = mid.replace('temp_', '').replace('_at_', '@').replace('_dot_', '.')
                    members_info.append({
                        'id': mid,
                        'email': temp_email,
                        'is_creator': mid == board.get('creator_id', '')
                    })
                else:
                    members_info.append({
                        'id': mid,
                        'email': f"User {mid[:6]}...",
                        'is_creator': mid == board.get('creator_id', '')
                    })
            
            return templates.TemplateResponse('add_member.html', {
                'request': request,
                'user_token': user_token,
                'error_message': "User is already a member of this board.",
                'success_message': None,
                'board': board,
                'members_info': members_info
            })

        members = board.get('members', [])
        members.append(member_id)
        
        # Update the board with new member and emails
        board_ref.update({
            'members': members,
            'member_emails': member_emails
        })
        
        updated_board = await get_task_board(board_id)
        
        # Get members info for the success response
        members_info = []
        for mid in updated_board.get('members', []):
            if mid in member_emails:
                members_info.append({
                    'id': mid,
                    'email': member_emails[mid],
                    'is_creator': mid == updated_board.get('creator_id', '')
                })
            elif mid == user_id:
                members_info.append({
                    'id': mid,
                    'email': user_token.get('email', 'Your account'),
                    'is_creator': mid == updated_board.get('creator_id', '')
                })
            elif mid.startswith('temp_'):
                temp_email = mid.replace('temp_', '').replace('_at_', '@').replace('_dot_', '.')
                members_info.append({
                    'id': mid,
                    'email': temp_email,
                    'is_creator': mid == updated_board.get('creator_id', '')
                })
            else:
                members_info.append({
                    'id': mid,
                    'email': f"User {mid[:6]}...",
                    'is_creator': mid == updated_board.get('creator_id', '')
                })

        return templates.TemplateResponse('add_member.html', {
            'request': request,
            'user_token': user_token,
            'error_message': None,
            'success_message': f"User {email} has been added to the board.",
            'board': updated_board,
            'members_info': members_info
        })

    except ValueError as err:
        print(str(err))
        return RedirectResponse(url="/")
    

# Route to check user in Firestore
@app.post("/ensure-user")

async def ensure_user(request: Request):

    try:

        data = await request.json()
        user_id = data.get('uid')
        email = data.get('email')

        if user_id and email:

            user_ref = db.collection('users').document(user_id)
            user = user_ref.get()
            
            if not user.exists:

                print(f"Creating new user record for {email}")

                user_data = {

                    'email': email,
                    'created_at': firestore.SERVER_TIMESTAMP
                }

                user_ref.set(user_data)

                return {"status": "created"}

            return {"status": "exists"}

        return {"status": "error", "message": "Missing user ID or email"}

    except Exception as e:

        print(f"Error ensuring user: {str(e)}")

        return {"status": "error", "message": str(e)}
    

    
# Create Task
@app.get("/board/{board_id}/create-task", response_class=HTMLResponse)
async def create_task_page(request: Request, board_id: str):
    id_token = request.cookies.get("token")
    error_message = None
    user_token = None
    board = None

    if not id_token:
        return RedirectResponse(url="/")
    
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']
        
        board = await get_task_board(board_id)
        
        if not board:
            return RedirectResponse(url="/")
        
        if user_id not in board.get('members', []):
            email = user_token.get('email', '')
            temp_user_id = f"temp_{email.replace('@', '_at_').replace('.', '_dot_')}"
            if temp_user_id not in board.get('members', []):
                return RedirectResponse(url="/")
        
        board_members = []
        member_emails = board.get('member_emails', {})
        
        for member_id in board.get('members', []):
            if member_id in member_emails:
                board_members.append({
                    'id': member_id,
                    'email': member_emails[member_id]
                })
            elif member_id == user_id:
                board_members.append({
                    'id': member_id,
                    'email': user_token.get('email', 'You')
                })
            elif member_id.startswith('temp_'):
                email = member_id.replace('temp_', '').replace('_at_', '@').replace('_dot_', '.')
                board_members.append({
                    'id': member_id,
                    'email': email
                })
            else:
                board_members.append({
                    'id': member_id,
                    'email': f"User {member_id[:6]}..."
                })
        
    except ValueError as err:
        print(str(err))
        return RedirectResponse(url="/")

    return templates.TemplateResponse('create_task.html', {
        'request': request,
        'user_token': user_token,
        'error_message': error_message,
        'board': board,
        'board_members': board_members
    })

@app.post("/board/{board_id}/create-task")
async def create_task_submit(
    request: Request, 
    board_id: str, 
    title: str = Form(...), 
    description: str = Form(""),
    due_date: str = Form(None),
    assigned_to: str = Form(None)
):
    id_token = request.cookies.get("token")
    
    if not id_token:
        return RedirectResponse(url="/")
    
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']
        
        board = await get_task_board(board_id)
        
        if not board:
            return RedirectResponse(url="/")
        
        if user_id not in board.get('members', []):
            email = user_token.get('email', '')
            temp_user_id = f"temp_{email.replace('@', '_at_').replace('.', '_dot_')}"
            if temp_user_id not in board.get('members', []):
                return RedirectResponse(url="/")
        
        assigned_users = []
        if assigned_to and assigned_to != "none":
            assigned_users = [assigned_to]
        
        task = await create_task(
            board_id=board_id,
            title=title,
            description=description,
            creator_id=user_id,
            assigned_users=assigned_users,
            due_date=due_date
        )
        
        return RedirectResponse(url=f"/board/{board_id}", status_code=303)
        
    except ValueError as err:
        print(str(err))
        return RedirectResponse(url="/")
    

# Routes for task marking
@app.post("/board/{board_id}/task/{task_id}/complete")

async def complete_task(request: Request, board_id: str, task_id: str):

    id_token = request.cookies.get("token")

    if not id_token:

        return RedirectResponse(url="/")

    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        user_id = user_token['user_id']
        board = await get_task_board(board_id)

        if not board:

            return RedirectResponse(url="/")

        if user_id not in board.get('members', []):

            email = user_token.get('email', '')

            temp_user_id = f"temp_{email.replace('@', '_at_').replace('.', '_dot_')}"

            if temp_user_id not in board.get('members', []):

                return RedirectResponse(url="/")

        task_ref = db.collection('task_boards').document(board_id).collection('tasks').document(task_id)

        task = task_ref.get()

        if not task.exists:

            return RedirectResponse(url=f"/board/{board_id}")

        import datetime

        task_ref.update({

            'status': 'completed',
            'completed_at': firestore.SERVER_TIMESTAMP

        })

        return RedirectResponse(url=f"/board/{board_id}", status_code=303)

    except ValueError as err:

        print(str(err))

        return RedirectResponse(url="/")
