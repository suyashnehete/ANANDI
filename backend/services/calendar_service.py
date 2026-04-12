import json
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class CalendarService:
    def __init__(self, app_data_dir: Path):
        self.calendar = None
        self.credentials_path = Path('credentials.json')
        self.token_path = app_data_dir / 'token.json'

    def _load_credentials(self) -> dict | None:
        if not self.credentials_path.exists():
            return None
        try:
            data = json.loads(self.credentials_path.read_text())
            return data.get('installed') or data.get('web')
        except Exception:
            return None

    def initialize(self) -> bool:
        try:
            credentials = self._load_credentials()
            if not credentials or not self.token_path.exists():
                return False

            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            token_data = json.loads(self.token_path.read_text())
            creds = Credentials.from_authorized_user_info(token_data)

            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.token_path.write_text(creds.to_json())

            self.calendar = build('calendar', 'v3', credentials=creds)
            return True
        except Exception as e:
            print(f'Calendar init error: {e}')
            self.calendar = None
            return False

    def get_status(self) -> dict:
        return {
            'configured': self._load_credentials() is not None,
            'hasToken': self.token_path.exists(),
            'connected': self.calendar is not None
        }

    def authorize(self) -> dict:
        try:
            credentials = self._load_credentials()
            if not credentials:
                return {
                    'success': False,
                    'error': 'Add credentials.json to the project folder before connecting Google Calendar.'
                }

            if self.initialize():
                return {'success': True, 'message': 'Google Calendar is already connected.'}

            from google_auth_oauthlib.flow import Flow

            redirect_uris = credentials.get('redirect_uris', ['http://localhost'])
            parsed = urlparse(redirect_uris[0])
            expected_path = parsed.path or '/'

            code_holder: dict = {'code': None, 'error': None}
            server_done = threading.Event()

            class OAuthHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    url = urlparse(self.path)
                    if url.path != expected_path:
                        self.send_response(404)
                        self.end_headers()
                        return
                    params = parse_qs(url.query)
                    error = params.get('error', [None])[0]
                    code = params.get('code', [None])[0]
                    if error:
                        code_holder['error'] = error
                        self.send_response(400)
                        self.send_header('Content-Type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b'<h1>Authorization failed.</h1><p>You can close this window.</p>')
                    elif code:
                        code_holder['code'] = code
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/html')
                        self.end_headers()
                        self.wfile.write(
                            b'<h1>Calendar connected.</h1>'
                            b'<p>You can close this window and return to Anandi.</p>'
                        )
                    else:
                        self.send_response(400)
                        self.end_headers()
                    server_done.set()

                def log_message(self, *args):
                    pass

            server = HTTPServer(('127.0.0.1', 0), OAuthHandler)
            port = server.server_address[1]
            redirect_uri = f'http://localhost:{port}{expected_path}'

            raw = self.credentials_path.read_text()
            raw_data = json.loads(raw)
            flow = Flow.from_client_config(
                raw_data,
                scopes=['https://www.googleapis.com/auth/calendar.readonly'],
                redirect_uri=redirect_uri
            )
            auth_url, _ = flow.authorization_url(access_type='offline', prompt='consent')

            server_thread = threading.Thread(target=server.handle_request, daemon=True)
            server_thread.start()

            webbrowser.open(auth_url)
            server_done.wait(timeout=120)

            if code_holder['error']:
                return {'success': False, 'error': f'Google authorization failed: {code_holder["error"]}'}
            if not code_holder['code']:
                return {'success': False, 'error': 'Google Calendar authorization timed out.'}

            flow.fetch_token(code=code_holder['code'])
            creds = flow.credentials
            self.token_path.write_text(creds.to_json())

            from googleapiclient.discovery import build
            self.calendar = build('calendar', 'v3', credentials=creds)
            return {'success': True, 'message': 'Google Calendar connected successfully.'}
        except Exception as e:
            print(f'Calendar auth error: {e}')
            return {'success': False, 'error': str(e) or 'Failed to connect Google Calendar.'}

    def get_today_events(self) -> list:
        if not self.calendar:
            return []
        try:
            now = datetime.now(timezone.utc)
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

            result = self.calendar.events().list(
                calendarId='primary',
                timeMin=start_of_day.isoformat(),
                timeMax=end_of_day.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = []
            for event in result.get('items', []):
                start = event.get('start', {})
                is_all_day = 'date' in start and 'dateTime' not in start
                if is_all_day:
                    time_str = 'All day'
                else:
                    dt = datetime.fromisoformat(start.get('dateTime', ''))
                    time_str = dt.strftime('%I:%M %p')
                events.append({
                    'title': event.get('summary', 'Untitled event'),
                    'time': time_str,
                    'description': event.get('description', '')
                })
            return events
        except Exception as e:
            print(f'Error fetching events: {e}')
            return []

    def get_upcoming_event(self) -> dict | None:
        events = self.get_today_events()
        now = datetime.now()
        for event in events:
            if event['time'] == 'All day':
                return event
            try:
                event_time = datetime.strptime(
                    f'{now.date().isoformat()} {event["time"]}', '%Y-%m-%d %I:%M %p'
                )
                if event_time > now:
                    return event
            except Exception:
                pass
        return None
