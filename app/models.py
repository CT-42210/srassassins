from datetime import datetime
import json
import uuid
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

def generate_uuid():
    return str(uuid.uuid4())

class Team(db.Model):
    __tablename__ = 'teams'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(100), nullable=False, unique=True)
    photo_path = db.Column(db.String(255), nullable=True)
    state = db.Column(db.String(20), default='pending')  # pending, alive, dead
    target_id = db.Column(db.String(36), db.ForeignKey('teams.id'), nullable=True)
    eliminations = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    players = db.relationship('Player', backref='team', lazy=True)
    target_team = db.relationship('Team', remote_side=[id], backref='targeting_teams', uselist=False)
    
    def __repr__(self):
        return f'<Team {self.name}>'
    
    @property
    def is_alive(self):
        return self.state == 'alive'
    
    @property
    def is_pending(self):
        return self.state == 'pending'
    
    @property
    def is_dead(self):
        return self.state == 'dead'
    
    @property
    def alive_players(self):
        return [player for player in self.players if player.is_alive]
    
    @property
    def all_dead(self):
        return all(not player.is_alive for player in self.players)

class Player(db.Model, UserMixin):
    __tablename__ = 'players'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password_hash = db.Column(db.String(128), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    state = db.Column(db.String(20), default='alive')  # alive, dead
    team_id = db.Column(db.String(36), db.ForeignKey('teams.id'), nullable=False)
    obituary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    kill_votes = db.relationship('KillVote', backref='voter', lazy=True)
    
    def __repr__(self):
        return f'<Player {self.name}>'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_alive(self):
        return self.state == 'alive'
    
    def set_obituary(self, kill_info):
        self.obituary = json.dumps(kill_info)
        self.state = 'dead'
    
    def get_obituary(self):
        if self.obituary:
            return json.loads(self.obituary)
        return None

class KillConfirmation(db.Model):
    __tablename__ = 'kill_confirmations'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    victim_id = db.Column(db.String(36), db.ForeignKey('players.id'), nullable=False)
    attacker_id = db.Column(db.String(36), db.ForeignKey('players.id'), nullable=False)
    kill_time = db.Column(db.DateTime, nullable=False)
    round_number = db.Column(db.Integer, nullable=False)
    video_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    expiration_time = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    victim = db.relationship('Player', foreign_keys=[victim_id], backref='victim_kill_confirmations')
    attacker = db.relationship('Player', foreign_keys=[attacker_id], backref='attacker_kill_confirmations')
    votes = db.relationship('KillVote', backref='kill_confirmation', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<KillConfirmation {self.attacker.name} -> {self.victim.name}>'
    
    @property
    def is_pending(self):
        return self.status == 'pending'
    
    @property
    def is_approved(self):
        return self.status == 'approved'
    
    @property
    def is_rejected(self):
        return self.status == 'rejected'
    
    @property
    def approve_votes(self):
        return sum(1 for vote in self.votes if vote.vote)
    
    @property
    def reject_votes(self):
        return sum(1 for vote in self.votes if not vote.vote)

class KillVote(db.Model):
    __tablename__ = 'kill_votes'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    kill_confirmation_id = db.Column(db.String(36), db.ForeignKey('kill_confirmations.id'), nullable=False)
    voter_id = db.Column(db.String(36), db.ForeignKey('players.id'), nullable=False)
    vote = db.Column(db.Boolean, nullable=False)  # True for approve, False for reject
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        vote_str = 'Approve' if self.vote else 'Reject'
        return f'<KillVote {self.voter.name}: {vote_str}>'

class GameState(db.Model):
    __tablename__ = 'game_state'
    
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(20), default='pre')  # pre, live, post, forced
    round_number = db.Column(db.Integer, default=0)
    voting_threshold = db.Column(db.Integer, default=3)
    round_start = db.Column(db.DateTime, nullable=True)
    round_end = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<GameState {self.state} Round {self.round_number}>'
    
    @property
    def is_pre(self):
        return self.state == 'pre'
    
    @property
    def is_live(self):
        return self.state == 'live'
    
    @property
    def is_post(self):
        return self.state == 'post'
    
    @property
    def is_forced(self):
        return self.state == 'forced'

class ActionLog(db.Model):
    __tablename__ = 'action_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    action_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    actor = db.Column(db.String(100), nullable=True)  # Can be admin, system, or player name
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ActionLog {self.action_type} by {self.actor}>'
