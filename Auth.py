import time
import json
import urllib
import requests
import threading
import webbrowser
import swagger_client
from pubsub import pub
from base64 import b64encode
from utils import settings, configFile
from swagger_client.rest import ApiException
from http.server import BaseHTTPRequestHandler, HTTPServer


#----------------------------------------------------------------------
def authenticate(forceLogin = False, forceRefresh = False) :
    """perform credentials operations and handles the code returned by the api"""
    if forceLogin:
        _credentials()
        _login()
    elif forceRefresh:
        _refresh()
    else:
        if not _validateAccessToken():
            _refresh()
        if not _validateAccessToken():
            raise ApiException(reason= "could not refresh token, login might be required")

#----------------------------------------------------------------------
def _validateAccessToken():
    """"""
    apiConfig = swagger_client.api_client.ApiClient()
    apiConfig.configuration.access_token = settings.accessToken
    apiConfig.default_headers = {'User-Agent': settings.userAgent}

    walletApi = swagger_client.WalletApi(apiConfig)

    try:
        walletApi.get_characters_character_id_wallet(1004487144)
        return True
    except ApiException:
        return False


#----------------------------------------------------------------------
def _credentials():
    """open a login window in the default browser so the user can authenticate"""
    scopes = ("publicData%20"
          "esi-skills.read_skills.v1%20"
          "esi-assets.read_corporation_assets.v1%20"
          "esi-corporations.read_blueprints.v1%20"
          "esi-markets.read_corporation_orders.v1%20"
          "esi-industry.read_corporation_jobs.v1%20"
          "esi-characters.read_blueprints.v1%20"
          "esi-wallet.read_corporation_wallets.v1%20"
          "esi-wallet.read_character_wallet.v1"
          )

    server = HTTPServer(('', int(settings.port)), CodeHandler)
    serverThread = threading.Thread(target=server.serve_forever)
    serverThread.daemon = True
    serverThread.start()
    webbrowser.open( (f'https://login.eveonline.com/oauth/authorize?'
                  f'response_type=code&'
                  f'redirect_uri=http://localhost:{settings.port}/&'
                  f'client_id={settings.clientID}&'
                  f'scope={scopes}&'
                  f'state=evesso') )


    while True:
        time.sleep(4)
        if hasattr(settings, 'code'):
            server.shutdown()
            break

#----------------------------------------------------------------------
def _login():
    """query ESI to retrieve access and refresh tokens"""
    headers = {'User-Agent':settings.userAgent}
    query = {'grant_type':'authorization_code','code': settings.code}
    secretEncoded = b64encode((settings.clientID+':'+settings.secret).encode()).decode()
    headers = {'Authorization':'Basic '+ secretEncoded,'User-Agent':settings.userAgent}
    r = requests.post(settings.authUrl,params=query,headers=headers)
    response = r.json()
    print(response)
    settings.accessToken = response['access_token']
    settings.refreshToken = response['refresh_token']
    _saveRefreshToken()

#----------------------------------------------------------------------
def _refresh():
    """query ESI to refresh an access token"""
    refreshToken = settings.refreshToken
    secretEncoded = b64encode((settings.clientID+':'+settings.secret).encode()).decode()
    headers = {'Authorization':'Basic '+ secretEncoded,'User-Agent':settings.userAgent}
    query = {'grant_type':'refresh_token','refresh_token':refreshToken}
    r = requests.post(settings.authUrl,params=query,headers=headers)
    response = r.json()
    settings.accessToken = response['access_token']
    settings.refreshToken = response['refresh_token']

    #save refresh token
    _saveRefreshToken()

#----------------------------------------------------------------------
def _saveRefreshToken():
    """save the refresh token to config.json"""
    #save refresh token
    settingDict = settings.__dict__.copy()
    settingDict.pop('code', None)


    with open(configFile, 'w') as config:
        json.dump(settingDict, config)

#This class is engineered as a handler for BaseHTTPRequest,
#it catches the authentication token after login.
#the original (and mostly unmodified) template from this
#comes from CREST-market-downloader from fuzzworks.
#note: i think this class inherits from BaseHTTPServer.BaseHTTPRequestHandler
class CodeHandler(BaseHTTPRequestHandler):
    """retrieve authentication token from localhost redirect after login"""
    def do_GET(self):
        if self.path == "/favicon.ico":
            return
        parsed_path = urllib.parse.urlparse(self.path)
        parts=urllib.parse.parse_qs(parsed_path.query)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Login successful. you can close this window now')
        pub.sendMessage('code', code = str(parts['code'][0]) )
        self.finish()
        self.connection.close()
    def log_message(self, format, *args):
        return

    def handle_one_request(self):
        """Handle a single HTTP request.

        You normally don't need to override this method; see the class
        __doc__ string for information on how to handle specific HTTP
        commands such as GET and POST.

        This method is almost exacly the same as in the base class, however,
        a "self.wfile.flush()" line at the end of this method was removed
        because it kept raising an exception about writing to closed files.

        """
        try:
            self.raw_requestline = self.rfile.readline(65537)
            if len(self.raw_requestline) > 65536:
                self.requestline = ''
                self.request_version = ''
                self.command = ''
                self.send_error(HTTPStatus.REQUEST_URI_TOO_LONG)
                return
            if not self.raw_requestline:
                self.close_connection = True
                return
            if not self.parse_request():
                # An error code has been sent, just exit
                return
            mname = 'do_' + self.command
            if not hasattr(self, mname):
                self.send_error(
                    HTTPStatus.NOT_IMPLEMENTED,
                    "Unsupported method (%r)" % self.command)
                return
            method = getattr(self, mname)
            method()
        except socket.timeout as e:
            #a read or a write timed out.  Discard this connection
            self.log_error("Request timed out: %r", e)
            self.close_connection = True
            return

if __name__ == "__main__":
    authenticate(forceLogin=True)