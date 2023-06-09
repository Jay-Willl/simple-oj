import json
from datetime import datetime

from flask import request
from flask_login import login_required, current_user
from sqlalchemy import select

from auth import filter
from problem.model import Problem, ProblemModel
from response import Response
from extentions import login_manager, bcrypt
from database import sql
from account.model import User
from upload.model import Upload, UploadModel
from event.model import Event, EventModel, Enrollment, EnrollmentModel, Containing, ContainingModel
from event import event_view


def get_max_assignment_id():
    max_id_assignment = Event.query.filter_by(type='assignment').order_by(Event.id.desc()).first()
    if max_id_assignment:
        return max_id_assignment.id
    else:
        return 1


def get_max_competition_id():
    max_id_competition = Event.query.filter_by(type='competition').order_by(Event.id.desc()).first()
    if max_id_competition:
        return max_id_competition.id
    else:
        return 1


def get_event_by_id(_id: int):
    event = sql.session.execute(select(Event).where(Event.id == _id))
    return event.fetchone()[0]


def get_all_competition():
    competition = sql.session.execute(select(Event).where(Event.type == 'competition'))
    return competition.fetchall()


def get_all_assignment():
    assignment = sql.session.execute(select(Event).where(Event.type == 'assignment'))
    return assignment.fetchall()


def get_upload_by_id(_user_id: int, _context_id: int):
    upload = sql.session.execute(select(Upload).where(Upload.user_id == _user_id and Upload.context_id == _context_id))
    if upload.first() is None:
        return None
    else:
        return sql.session.execute(select(Upload).where(Upload.user_id == _user_id and Upload.context_id == _context_id)).fetchone()[0]


def get_competition_enrollment_by_id(_id: int):
    enrollments = sql.session.query(Enrollment).filter(Enrollment.user_id == _id)
    results = []
    for enrollment in enrollments.all():
        temp_event: Event = get_event_by_id(enrollment.event_id)
        if temp_event.type == 'competition':
            results.append(temp_event)
    return [_event.to_json_lite() for _event in results]


def get_assignment_enrollment_by_id(_id: int):
    enrollments = sql.session.query(Enrollment).filter(Enrollment.user_id == _id)
    results = []
    for enrollment in enrollments.all():
        temp_event: Event = get_event_by_id(enrollment.event_id)
        if temp_event.type == 'assignment':
            results.append(temp_event)
    return [_event.to_json_lite() for _event in results]



@event_view.route('/assignment_id', methods=['POST'])
def get_assignment_id():
    content = request.get_json()
    r = Response()
    r.status_code = 200
    r.data = get_assignment_enrollment_by_id(content.get('user_id'))
    return r.to_json()


@event_view.route('/competition_id', methods=['POST'])
def get_competition_id():
    content = request.get_json()
    r = Response()
    r.status_code = 200
    r.data = get_competition_enrollment_by_id(content.get('user_id'))
    return r.to_json()


@event_view.route('/competition')
def get_competitions():
    r = Response()
    r.status_code = 200
    temp_events = Event.query.filter_by(type='competition').all()
    r.data = [_event.to_json_lite() for _event in temp_events]
    return r.to_json()


@event_view.route('/assignment')
def get_assignments():
    r = Response()
    r.status_code = 200
    temp_events = Event.query.filter_by(type='assignment').all()
    r.data = [_event.to_json_lite() for _event in temp_events]
    return r.to_json()


@event_view.route('/create_assignment', methods=['POST'])
def create_assignment():
    content = request.get_json()
    r = Response()
    try:
        event_model = EventModel(**content, type='assignment')
    except ValueError:
        r.message = 'invalid param'
        r.status_code = 406
        return r.to_json()
    event_dict = event_model.dict()
    temp_assignment: Event = Event(**event_dict)
    sql.session.add(temp_assignment)
    sql.session.commit()
    temp_assignment.id = get_max_assignment_id()
    return str(temp_assignment.id)


@event_view.route('/create_competition', methods=['POST'])
def create_competition():
    content = request.get_json()
    r = Response()
    try:
        event_model = EventModel(**content, type='competition')
    except ValueError:
        r.message = 'invalid param'
        r.status_code = 406
        return r.to_json()
    event_dict = event_model.dict()
    temp_competition: Event = Event(**event_dict)
    sql.session.add(temp_competition)
    sql.session.commit()
    temp_competition.id = get_max_competition_id()
    # create containing relations
    for problem in content.get('problems'):
        containing_model = ContainingModel(event_id=temp_competition.id, problem_id=int(problem))
        temp_containing: Containing = Containing(**containing_model.dict())
        sql.session.add(temp_containing)
        sql.session.commit()
    return str(temp_competition.id)


@event_view.route('/assignment_detail', methods=['POST'])
def assignment_detail():
    content = request.get_json()
    r = Response()
    temp_assignment: Event = get_event_by_id(content.get('event_id'))
    r.data = temp_assignment.to_json()
    r.status_code = 200
    return r.to_json()


@event_view.route('/competition_detail', methods=['POST'])
def competition_detail():
    content = request.get_json()
    r = Response()
    temp_competition: Event = get_event_by_id(content.get('event_id'))
    r.data = temp_competition.to_json()
    r.status_code = 200
    return r.to_json()


@event_view.route('/backward', methods=['POST'])
def back_detail():
    content = request.get_json()
    r = Response()
    temp_upload: Upload = get_upload_by_id(content.get('user_id'), content.get('event_id'))
    if temp_upload:
        r.data = temp_upload.to_json()
        r.status_code = 200
        return r.to_json()
    else:
        temp_upload = Upload()
        temp_upload.grade = -1
        temp_upload.comment = ""
        r.data = temp_upload.to_json()
        r.status_code = 200
        return r.to_json()


def get_problems_in_competition(_id: int):
    problems = sql.session.execute(select(Containing).where(Containing.event_id == _id))
    return problems.all()

def get_problem_by_id(_id: int):
    problem = sql.session.execute(select(Problem).where(Problem.id == _id))
    return problem.fetchone()[0]


@event_view.route('/details', methods=['POST'])
def get_details():
    content = request.get_json()
    r = Response()
    result = []
    for record in get_problems_in_competition(content.get('event_id')):
        result.append(get_problem_by_id(record[0].problem_id))
    r.data = [_problem.to_json_lite() for _problem in result]
    r.status_code = 200
    return r.to_json()
