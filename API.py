from BaseHTTPServer import BaseHTTPRequestHandler,HTTPServer
import threading
import urlparse
import base64
import os
import webbrowser
import json
import csv
import requests
import grequests
import time
import pubsub
import locale
from staticClasses import StaticData, Settings
import pickle
import eveapi
import httplib
import urllib
import copy
import zlib
import os
from xml.parsers import expat
from time import strptime
from calendar import timegm
from os.path import join, exists
import cPickle
import tempfile

proxy = None
proxySSL = False

########################################################################
class DataRequest:
  """request data to APIs, either ESI or XML"""
  
  #----------------------------------------------------------------------
  @classmethod
  def getAssets(cls, charID): 
    """query esi for asset data"""
    cacheName = str(charID) + "Assets.cache"
    objIdentifier = str(charID) + "Assets"
    
    #checking existance of object
    if objIdentifier in Settings.DataObjectStorage:
      return Settings.DataObjectStorage[objIdentifier]
    else:
    #checking existance and age
      try:
        lastModified = time.time() - os.path.getmtime("cache/"+cacheName)
      except:
        lastModified = 999999999999
        
      #obtaining data                      
      if lastModified < 3600:
        #loading cache
        pickleIn = open("cache/"+cacheName, 'rb')
        assets = pickle.load(pickleIn)
        pickleIn.close()
        return assets
      else:
        #getting data from api
        esi = ESI(charID)
        assetUrl = 'https://esi.tech.ccp.is/latest/characters/{}/assets/'.format(charID)
        r = requests.get(assetUrl, headers=esi.authHeader)
        assets = Assets(r.json())
        
        #saving cache
        if not os.path.isdir('cache'):
          os.mkdir('cache')
        pickleOut = open("cache/"+cacheName, 'wb')
        pickle.dump(assets, pickleOut) 
    
        Settings.DataObjectStorage[objIdentifier] = assets
        return assets
  
  #----------------------------------------------------------------------
  @classmethod
  def getSkills(cls, charID):
    """query esi for skill data"""
    cacheName = str(charID) + "Skill.cache"
    objIdentifier = str(charID) + "Skill"
    
    #checking existance of object
    if objIdentifier in Settings.DataObjectStorage:
      return Settings.DataObjectStorage[objIdentifier]
    else:    
      #checking existance and age
      try:
        lastModified = time.time() - os.path.getmtime("cache/"+cacheName)
      except:
        lastModified = 999999999999
        
      #obtaining data
      if lastModified < 3600:
        pickleIn = open("cache/"+cacheName, 'rb')
        skills = pickle.load(pickleIn)
        return skills
      else:
        #getting data from api    
        esi = ESI(charID)
        skillsUrl = 'https://esi.tech.ccp.is/latest/characters/{}/skills/?datasource=tranquility'.format(charID)
        r = requests.get(skillsUrl, headers=esi.authHeader)
        skills = Skills(r.json())
        
        #saving cache
        if not os.path.isdir('cache'):
          os.mkdir('cache')
        pickleOut = open("cache/"+cacheName, 'wb')
        pickle.dump(skills, pickleOut)       
        
        Settings.DataObjectStorage[objIdentifier] = skills
        return skills
  
  #----------------------------------------------------------------------
  @classmethod
  def getMarketHistory(cls, charID, typeID): 
    """query esi for market history data"""
    cacheName = str(charID) + "marketHistory" + str(typeID)+ ".cache"
    objIdentifier = str(charID) + "marketHistory" + str(typeID)
    
    #checking existance of object
    if objIdentifier in Settings.DataObjectStorage:
      return Settings.DataObjectStorage[objIdentifier]
    else:    
      #checking existance and age
      try:
        lastModified = time.time() - os.path.getmtime("cache/"+cacheName)
      except:
        lastModified = 999999999999
        
      #obtaining data    
      if lastModified < 3600:
        #lastModified = os.path.getmtime("cache/"+cacheName)
        pickleIn = open("cache/"+cacheName, 'rb')
        marketHistory = pickle.load(pickleIn)
        return marketHistory
      else:
        #getting data from api        
        esi = ESI(charID)
        marketHistoryUrl = 'https://esi.tech.ccp.is/latest/markets/{}/history/?type_id={}'.format(Settings.fadeID, typeID)
        r = requests.get(marketHistoryUrl, headers=esi.authHeader)
        marketHistory = MarketHistory(r.json())
        
        #saving cache
        if not os.path.isdir('cache'):
          os.mkdir('cache')
        pickleOut = open("cache/"+cacheName, 'wb')
        pickle.dump(marketHistory, pickleOut)            
        
        Settings.DataObjectStorage[objIdentifier] = marketHistory
        return marketHistory    
    
  #----------------------------------------------------------------------
  @classmethod
  def getBlueprints(cls, charID):
    """"""
    objIdentifier = str(charID) + "blueprints"
    if objIdentifier in Settings.DataObjectStorage:
      return Settings.DataObjectStorage[objIdentifier]
    else:    
      keyID = Settings.charConfig[charID]['KEYID']
      vCode = Settings.charConfig[charID]['VCODE']
      
      cachedApi = EVEAPIConnection(cacheHandler=MyCacheHandler(debug=Settings.debug))
      xml = cachedApi.auth(keyID=keyID, vCode=vCode).character(charID)
      return xml.Blueprints()

  #----------------------------------------------------------------------
  @classmethod
  def getMarketOrders(cls, charID):
    """obtain data about market orders for given character"""
    objIdentifier = str(charID) + "marketOrders"
    if objIdentifier in Settings.DataObjectStorage:
      return Settings.DataObjectStorage[objIdentifier]
    else:
      keyID = Settings.charConfig[charID]['KEYID']
      vCode = Settings.charConfig[charID]['VCODE']
      
      cachedApi = eveapi.EVEAPIConnection(cacheHandler=eveapi.MyCacheHandler(debug=Settings.debug))
      xml = cachedApi.auth(keyID=keyID, vCode=vCode).character(charID)
      marketOrders = MarketOrders(xml.MarketOrders().orders)
      
      Settings.DataObjectStorage[objIdentifier] = marketOrders
      return marketOrders
    
    
  #----------------------------------------------------------------------
  @classmethod
  def getIndustryJobs(cls, charID):
    """obtain data about market orders for given character"""
    objIdentifier = str(charID) + "Jobs"
    if objIdentifier in Settings.DataObjectStorage:
      return Settings.DataObjectStorage[objIdentifier]
    else:
      keyID = Settings.charConfig[charID]['KEYID']
      vCode = Settings.charConfig[charID]['VCODE']
      
      cachedApi = EVEAPIConnection(cacheHandler=MyCacheHandler(debug=Settings.debug))
      xml = cachedApi.auth(keyID=keyID, vCode=vCode).character(charID)
      ind = xml.IndustryJobs()

      return ind  





########################################################################
class ESI:
  """take care of login and authentication operations for the ESI interface"""

  #----------------------------------------------------------------------
  def __init__(self, charID):
    """Constructor, perform credentials operations and handles the code returned by the api"""
    self.charID = charID
    if Settings.config.has_option(charID, 'ACCESSTOKEN'):
      self.authHeader = {'Authorization':'Bearer '+ Settings.charConfig[charID]['ACCESSTOKEN'],'User-Agent': Settings.userAgent}
    elif Settings.charConfig[charID]['REFRESHTOKEN']:
      self._refresh()
      self.authHeader = {'Authorization':'Bearer '+ Settings.charConfig[charID]['ACCESSTOKEN'],'User-Agent': Settings.userAgent}
    else:
      self._credentials()
      self._login()
      self.authHeader = {'Authorization':'Bearer '+ Settings.charConfig[charID]['ACCESSTOKEN'],'User-Agent': Settings.userAgent}
    
  #----------------------------------------------------------------------
  def _credentials(self):
    """"""
    scopes = "esi-assets.read_assets.v1%20esi-planets.manage_planets.v1%20publicData%20esi-wallet.read_character_wallet.v1%20esi-skills.read_skillqueue.v1%20esi-skills.read_skills.v1"

    server = HTTPServer(('', int(Settings.port)), CodeHandler)
    serverThread = threading.Thread(target=server.serve_forever)
    serverThread.daemon = True
    serverThread.start()  
    webbrowser.open('https://login.eveonline.com/oauth/authorize?response_type=code&redirect_uri=http://localhost:'+Settings.port+'/&client_id='+Settings.clientID+'&scope='+scopes+'&state=') #%20%20%20%20%20%20%20%20%20%20%20%20%20%20  %20%20%20%20
    Settings.updateCode(self.charID)         
      
  #----------------------------------------------------------------------
  def _login(self):
    """"""
    headers = {'User-Agent':Settings.userAgent}
    query = {'grant_type':'authorization_code','code': Settings.charConfig[self.charID]['CODE']}
    headers = {'Authorization':'Basic '+ base64.b64encode(Settings.clientID+':'+Settings.secret),'User-Agent':Settings.userAgent}
    r = requests.post(Settings.authUrl,params=query,headers=headers) 
    response = r.json()
    Settings.charConfig[self.charID]['ACCESSTOKEN'] = response['access_token']
    Settings.charConfig[self.charID]['REFRESHTOKEN'] = response['refresh_token']  
    self._saveRefreshToken()
    
  #----------------------------------------------------------------------
  def _refresh(self):
    """handle token refresh requests"""
    refreshToken = Settings.charConfig[self.charID]['REFRESHTOKEN']
    headers = {'Authorization':'Basic '+ base64.b64encode(Settings.clientID+':'+Settings.secret),'User-Agent':Settings.userAgent}
    query = {'grant_type':'refresh_token','refresh_token':refreshToken}
    r = requests.post(Settings.authUrl,params=query,headers=headers)
    response = r.json()
    Settings.charConfig[self.charID]['ACCESSTOKEN'] = response['access_token']
    Settings.charConfig[self.charID]['REFRESHTOKEN'] = response['refresh_token']  
    #save refresh token
    self._saveRefreshToken()
  
  #----------------------------------------------------------------------
  def _saveRefreshToken(self):
    """save the refresh token to config.ini"""
    #save refresh token
    refreshToken = Settings.charConfig[self.charID]['REFRESHTOKEN']
    Settings.config.set(str(self.charID), 'REFRESHTOKEN', refreshToken)
    fileHandle = open(Settings.iniPath, 'w')
    Settings.config.write(fileHandle)
    fileHandle.close()




#-----------------------------------------------------------------------------
class MyCacheHandler(object):
  # Note: this is an example handler to demonstrate how to use them.
  # a -real- handler should probably be thread-safe and handle errors
  # properly (and perhaps use a better hashing scheme).

  def __init__(self, debug=False):
    self.debug = debug
    self.count = 0
    self.cache = {}
    self.tempdir = join(tempfile.gettempdir(), "eveapi")
    if not exists(self.tempdir):
      os.makedirs(self.tempdir)

  def log(self, what):
    if self.debug:
      print "[%d] %s" % (self.count, what)

  def retrieve(self, host, path, params):
    # eveapi asks if we have this request cached
    key = hash((host, path, frozenset(params.items())))

    self.count += 1  # for logging

    # see if we have the requested page cached...
    cached = self.cache.get(key, None)
    if cached:
      cacheFile = None
      #print "'%s': retrieving from memory" % path
    else:
      # it wasn't cached in memory, but it might be on disk.
      cacheFile = join(self.tempdir, str(key) + ".cache")
      if exists(cacheFile):
        self.log("%s: retrieving from disk" % path)
        f = open(cacheFile, "rb")
        cached = self.cache[key] = cPickle.loads(zlib.decompress(f.read()))
        f.close()

    if cached:
      # check if the cached doc is fresh enough
      if time.time() < cached[0]:
        self.log("%s: returning cached document" % path)
        return cached[1]  # return the cached XML doc

      # it's stale. purge it.
      self.log("%s: cache expired, purging!" % path)
      del self.cache[key]
      if cacheFile:
        os.remove(cacheFile)

    self.log("%s: not cached, fetching from server..." % path)
    # we didn't get a cache hit so return None to indicate that the data
    # should be requested from the server.
    return None

  def store(self, host, path, params, doc, obj):
    # eveapi is asking us to cache an item
    key = hash((host, path, frozenset(params.items())))

    cachedFor = obj.cachedUntil - obj.currentTime
    if cachedFor:
      self.log("%s: cached (%d seconds)" % (path, cachedFor))

      cachedUntil = time.time() + cachedFor

      # store in memory
      cached = self.cache[key] = (cachedUntil, doc)

      # store in cache folder
      cacheFile = join(self.tempdir, str(key) + ".cache")
      f = open(cacheFile, "wb")
      f.write(zlib.compress(cPickle.dumps(cached, -1)))
      f.close()



def set_cast_func(func):
  """Sets an alternative value casting function for the XML parser.
  The function must have 2 arguments; key and value. It should return a
  value or object of the type appropriate for the given attribute name/key.
  func may be None and will cause the default _autocast function to be used.
  """
  global _castfunc
  _castfunc = _autocast if func is None else func


class Error(StandardError):
  def __init__(self, code, message):
    self.code = code
    self.args = (message.rstrip("."),)
  def __unicode__(self):
    return u'%s [code=%s]' % (self.args[0], self.code)

class RequestError(Error):
  pass

class AuthenticationError(Error):
  pass

class ServerError(Error):
  pass


def EVEAPIConnection(url="api.eveonline.com", cacheHandler=None, proxy=None, proxySSL=False):
  # Creates an API object through which you can call remote functions.
  #
  # The following optional arguments may be provided:
  #
  # url - root location of the EVEAPI server
  #
  # proxy - (host,port) specifying a proxy server through which to request
  #         the API pages. Specifying a proxy overrides default proxy.
  #
  # proxySSL - True if the proxy requires SSL, False otherwise.
  #
  # cacheHandler - an object which must support the following interface:
  #
  #      retrieve(host, path, params)
  #
  #          Called when eveapi wants to fetch a document.
  #          host is the address of the server, path is the full path to
  #          the requested document, and params is a dict containing the
  #          parameters passed to this api call (keyID, vCode, etc).
  #          The method MUST return one of the following types:
  #
  #           None - if your cache did not contain this entry
  #           str/unicode - eveapi will parse this as XML
  #           Element - previously stored object as provided to store()
  #           file-like object - eveapi will read() XML from the stream.
  #
  #      store(host, path, params, doc, obj)
  #
  #          Called when eveapi wants you to cache this item.
  #          You can use obj to get the info about the object (cachedUntil
  #          and currentTime, etc) doc is the XML document the object
  #          was generated from. It's generally best to cache the XML, not
  #          the object, unless you pickle the object. Note that this method
  #          will only be called if you returned None in the retrieve() for
  #          this object.
  #

  if not url.startswith("http"):
    url = "https://" + url
  p = urlparse.urlparse(url, "https")
  if p.path and p.path[-1] == "/":
    p.path = p.path[:-1]
  ctx = _RootContext(None, p.path, {}, {})
  ctx._handler = cacheHandler
  ctx._scheme = p.scheme
  ctx._host = p.netloc
  ctx._proxy = proxy or globals()["proxy"]
  ctx._proxySSL = proxySSL or globals()["proxySSL"]
  return ctx


def ParseXML(file_or_string):
  try:
    return _ParseXML(file_or_string, False, None)
  except TypeError:
    raise TypeError("XML data must be provided as string or file-like object")


def _ParseXML(response, fromContext, storeFunc):
  # pre/post-process XML or Element data

  if fromContext and isinstance(response, Element):
    obj = response
  elif type(response) in (str, unicode):
    obj = _Parser().Parse(response, False)
  elif hasattr(response, "read"):
    obj = _Parser().Parse(response, True)
  else:
    raise TypeError("retrieve method must return None, string, file-like object or an Element instance")

  error = getattr(obj, "error", False)
  if error:
    if error.code >= 500:
      raise ServerError(error.code, error.data)
    elif error.code >= 200:
      raise AuthenticationError(error.code, error.data)
    elif error.code >= 100:
      raise RequestError(error.code, error.data)
    else:
      raise Error(error.code, error.data)

  result = getattr(obj, "result", False)
  if not result:
    raise RuntimeError("API object does not contain result")

  if fromContext and storeFunc:
    # call the cache handler to store this object
    storeFunc(obj)

  # make metadata available to caller somehow
  result._meta = obj

  return result





#-----------------------------------------------------------------------------
# API Classes
#-----------------------------------------------------------------------------

_listtypes = (list, tuple, dict)
_unspecified = []

class _Context(object):

  def __init__(self, root, path, parentDict, newKeywords=None):
    self._root = root or self
    self._path = path
    if newKeywords:
      if parentDict:
        self.parameters = parentDict.copy()
      else:
        self.parameters = {}
      self.parameters.update(newKeywords)
    else:
      self.parameters = parentDict or {}

  def context(self, *args, **kw):
    if kw or args:
      path = self._path
      if args:
        path += "/" + "/".join(args)
      return self.__class__(self._root, path, self.parameters, kw)
    else:
      return self

  def __getattr__(self, this):
    # perform arcane attribute majick trick
    return _Context(self._root, self._path + "/" + this, self.parameters)

  def __call__(self, **kw):
    if kw:
      # specified keywords override contextual ones
      for k, v in self.parameters.iteritems():
        if k not in kw:
          kw[k] = v
    else:
      # no keywords provided, just update with contextual ones.
      kw.update(self.parameters)

    # now let the root context handle it further
    return self._root(self._path, **kw)


class _AuthContext(_Context):

  def character(self, characterID):
    # returns a copy of this connection object but for every call made
    # through it, it will add the folder "/char" to the url, and the
    # characterID to the parameters passed.
    return _Context(self._root, self._path + "/char", self.parameters, {"characterID":characterID})

  def corporation(self, characterID):
    # same as character except for the folder "/corp"
    return _Context(self._root, self._path + "/corp", self.parameters, {"characterID":characterID})


class _RootContext(_Context):

  def auth(self, **kw):
    if len(kw) == 2 and (("keyID" in kw and "vCode" in kw) or ("userID" in kw and "apiKey" in kw)):
      return _AuthContext(self._root, self._path, self.parameters, kw)
    raise ValueError("Must specify keyID and vCode")

  def setcachehandler(self, handler):
    self._root._handler = handler

  def __call__(self, path, **kw):
    # convert list type arguments to something the API likes
    for k, v in kw.iteritems():
      if isinstance(v, _listtypes):
        kw[k] = ','.join(map(str, list(v)))

    cache = self._root._handler

    # now send the request
    path += ".xml.aspx"

    if cache:
      response = cache.retrieve(self._host, path, kw)
    else:
      response = None

    if response is None:
      if self._proxy is None:
        req = path
        if self._scheme == "https":
          conn = httplib.HTTPSConnection(self._host)
        else:
          conn = httplib.HTTPConnection(self._host)
      else:
        req = self._scheme+'://'+self._host+path
        if self._proxySSL:
          conn = httplib.HTTPSConnection(*self._proxy)
        else:
          conn = httplib.HTTPConnection(*self._proxy)

      if kw:
        conn.request("POST", req, urllib.urlencode(kw), {"Content-type": "application/x-www-form-urlencoded"})
      else:
        conn.request("GET", req)

      response = conn.getresponse()
      if response.status != 200:
        if response.status == httplib.NOT_FOUND:
          raise AttributeError("'%s' not available on API server (404 Not Found)" % path)
        elif response.status == httplib.FORBIDDEN:
          raise AuthenticationError(response.status, 'HTTP 403 - Forbidden')
        else:
          raise ServerError(response.status, "'%s' request failed (%s)" % (path, response.reason))

      if cache:
        store = True
        response = response.read()
      else:
        store = False
    else:
      store = False

    retrieve_fallback = cache and getattr(cache, "retrieve_fallback", False)
    if retrieve_fallback:
      # implementor is handling fallbacks...
      try:
        return _ParseXML(response, True, store and (lambda obj: cache.store(self._host, path, kw, response, obj)))
      except Error, e:
        response = retrieve_fallback(self._host, path, kw, reason=e)
        if response is not None:
          return response
        raise
    else:
      # implementor is not handling fallbacks...
      return _ParseXML(response, True, store and (lambda obj: cache.store(self._host, path, kw, response, obj)))

#-----------------------------------------------------------------------------
# XML Parser
#-----------------------------------------------------------------------------

def _autocast(key, value):
  # attempts to cast an XML string to the most probable type.
  try:
    if value.strip("-").isdigit():
      return int(value)
  except ValueError:
    pass

  try:
    return float(value)
  except ValueError:
    pass

  if len(value) == 19 and value[10] == ' ':
    # it could be a date string
    try:
      return max(0, int(timegm(strptime(value, "%Y-%m-%d %H:%M:%S"))))
    except OverflowError:
      pass
    except ValueError:
      pass

  # couldn't cast. return string unchanged.
  return value

_castfunc = _autocast


class _Parser(object):

  def Parse(self, data, isStream=False):
    self.container = self.root = None
    self._cdata = False
    p = expat.ParserCreate()
    p.StartElementHandler = self.tag_start
    p.CharacterDataHandler = self.tag_cdata
    p.StartCdataSectionHandler = self.tag_cdatasection_enter
    p.EndCdataSectionHandler = self.tag_cdatasection_exit
    p.EndElementHandler = self.tag_end
    p.ordered_attributes = True
    p.buffer_text = True

    if isStream:
      p.ParseFile(data)
    else:
      p.Parse(data, True)
    return self.root


  def tag_cdatasection_enter(self):
    # encountered an explicit CDATA tag.
    self._cdata = True

  def tag_cdatasection_exit(self):
    if self._cdata:
      # explicit CDATA without actual data. expat doesn't seem
      # to trigger an event for this case, so do it manually.
      # (_cdata is set False by this call)
      self.tag_cdata("")
    else:
      self._cdata = False

  def tag_start(self, name, attributes):
    # <hack>
    # If there's a colon in the tag name, cut off the name from the colon
    # onward. This is a workaround to make certain bugged XML responses
    # (such as eve/CharacterID.xml.aspx) work.
    if ":" in name:
      name = name[:name.index(":")]
    # </hack>

    if name == "rowset":
      # for rowsets, use the given name
      try:
        columns = attributes[attributes.index('columns')+1].replace(" ", "").split(",")
      except ValueError:
        # rowset did not have columns tag set (this is a bug in API)
        # columns will be extracted from first row instead.
        columns = []

      try:
        priKey = attributes[attributes.index('key')+1]
        this = IndexRowset(cols=columns, key=priKey)
      except ValueError:
        this = Rowset(cols=columns)


      this._name = attributes[attributes.index('name')+1]
      this.__catch = "row" # tag to auto-add to rowset.
    else:
      this = Element()
      this._name = name

    this.__parent = self.container

    if self.root is None:
      # We're at the root. The first tag has to be "eveapi" or we can't
      # really assume the rest of the xml is going to be what we expect.
      if name != "eveapi":
        raise RuntimeError("Invalid API response")
      try:
        this.version = attributes[attributes.index("version")+1]
      except KeyError:
        raise RuntimeError("Invalid API response")
      self.root = this

    if isinstance(self.container, Rowset) and (self.container.__catch == this._name):
      # <hack>
      # - check for missing columns attribute (see above).
      # - check for missing row attributes.
      # - check for extra attributes that were not defined in the rowset,
      #   such as rawQuantity in the assets lists.
      # In either case the tag is assumed to be correct and the rowset's
      # columns are overwritten with the tag's version, if required.
      numAttr = len(attributes)/2
      numCols = len(self.container._cols)
      if numAttr < numCols and (attributes[-2] == self.container._cols[-1]):
        # the row data is missing attributes that were defined in the rowset.
        # missing attributes' values will be set to None.
        fixed = []
        row_idx = 0; hdr_idx = 0; numAttr*=2
        for col in self.container._cols:
          if col == attributes[row_idx]:
            fixed.append(_castfunc(col, attributes[row_idx+1]))
            row_idx += 2
          else:
            fixed.append(None)
          hdr_idx += 1
        self.container.append(fixed)
      else:
        if not self.container._cols or (numAttr > numCols):
          # the row data contains more attributes than were defined.
          self.container._cols = attributes[0::2]
        self.container.append([_castfunc(attributes[i], attributes[i+1]) for i in xrange(0, len(attributes), 2)])
      # </hack>

      this._isrow = True
      this._attributes = this._attributes2 = None
    else:
      this._isrow = False
      this._attributes = attributes
      this._attributes2 = []

    self.container = self._last = this
    self.has_cdata = False

  def tag_cdata(self, data):
    self.has_cdata = True
    if self._cdata:
      # unset cdata flag to indicate it's been handled.
      self._cdata = False
    else:
      if data in ("\r\n", "\n") or data.strip() != data:
        return

    this = self.container
    data = _castfunc(this._name, data)

    if this._isrow:
      # sigh. anonymous data inside rows makes Entity cry.
      # for the love of Jove, CCP, learn how to use rowsets.
      parent = this.__parent
      _row = parent._rows[-1]
      _row.append(data)
      if len(parent._cols) < len(_row):
        parent._cols.append("data")

    elif this._attributes:
      # this tag has attributes, so we can't simply assign the cdata
      # as an attribute to the parent tag, as we'll lose the current
      # tag's attributes then. instead, we'll assign the data as
      # attribute of this tag.
      this.data = data
    else:
      # this was a simple <tag>data</tag> without attributes.
      # we won't be doing anything with this actual tag so we can just
      # bind it to its parent (done by __tag_end)
      setattr(this.__parent, this._name, data)

  def tag_end(self, name):
    this = self.container

    if this is self.root:
      del this._attributes
      #this.__dict__.pop("_attributes", None)
      return

    # we're done with current tag, so we can pop it off. This means that
    # self.container will now point to the container of element 'this'.
    self.container = this.__parent
    del this.__parent

    attributes = this.__dict__.pop("_attributes")
    attributes2 = this.__dict__.pop("_attributes2")
    if attributes is None:
      # already processed this tag's closure early, in tag_start()
      return

    if self.container._isrow:
      # Special case here. tags inside a row! Such tags have to be
      # added as attributes of the row.
      parent = self.container.__parent

      # get the row line for this element from its parent rowset
      _row = parent._rows[-1]

      # add this tag's value to the end of the row
      _row.append(getattr(self.container, this._name, this))

      # fix columns if neccessary.
      if len(parent._cols) < len(_row):
        parent._cols.append(this._name)
    else:
      # see if there's already an attribute with this name (this shouldn't
      # really happen, but it doesn't hurt to handle this case!
      sibling = getattr(self.container, this._name, None)
      if sibling is None:
        if (not self.has_cdata) and (self._last is this) and (name != "rowset"):
          if attributes:
            # tag of the form <tag attribute=bla ... />
            e = Element()
            e._name = this._name
            setattr(self.container, this._name, e)
            for i in xrange(0, len(attributes), 2):
              setattr(e, attributes[i], attributes[i+1])
          else:
            # tag of the form: <tag />, treat as empty string.
            setattr(self.container, this._name, "")
        else:
          self.container._attributes2.append(this._name)
          setattr(self.container, this._name, this)

      # Note: there aren't supposed to be any NON-rowset tags containing
      # multiples of some tag or attribute. Code below handles this case.
      elif isinstance(sibling, Rowset):
        # its doppelganger is a rowset, append this as a row to that.
        row = [_castfunc(attributes[i], attributes[i+1]) for i in xrange(0, len(attributes), 2)]
        row.extend([getattr(this, col) for col in attributes2])
        sibling.append(row)
      elif isinstance(sibling, Element):
        # parent attribute is an element. This means we're dealing
        # with multiple of the same sub-tag. Change the attribute
        # into a Rowset, adding the sibling element and this one.
        rs = Rowset()
        rs.__catch = rs._name = this._name
        row = [_castfunc(attributes[i], attributes[i+1]) for i in xrange(0, len(attributes), 2)]+[getattr(this, col) for col in attributes2]
        rs.append(row)
        row = [getattr(sibling, attributes[i]) for i in xrange(0, len(attributes), 2)]+[getattr(sibling, col) for col in attributes2]
        rs.append(row)
        rs._cols = [attributes[i] for i in xrange(0, len(attributes), 2)]+[col for col in attributes2]
        setattr(self.container, this._name, rs)
      else:
        # something else must have set this attribute already.
        # (typically the <tag>data</tag> case in tag_data())
        pass

    # Now fix up the attributes and be done with it.
    for i in xrange(0, len(attributes), 2):
      this.__dict__[attributes[i]] = _castfunc(attributes[i], attributes[i+1])

    return




#-----------------------------------------------------------------------------
# XML Data Containers
#-----------------------------------------------------------------------------
# The following classes are the various container types the XML data is
# unpacked into.
#
# Note that objects returned by API calls are to be treated as read-only. This
# is not enforced, but you have been warned.
#-----------------------------------------------------------------------------

class Element(object):
  # Element is a namespace for attributes and nested tags
  def __str__(self):
    return "<Element '%s'>" % self._name

_fmt = u"%s:%s".__mod__
class Row(object):
  # A Row is a single database record associated with a Rowset.
  # The fields in the record are accessed as attributes by their respective
  # column name.
  #
  # To conserve resources, Row objects are only created on-demand. This is
  # typically done by Rowsets (e.g. when iterating over the rowset).

  def __init__(self, cols=None, row=None):
    self._cols = cols or []
    self._row = row or []

  def __nonzero__(self):
    return True

  def __ne__(self, other):
    return self.__cmp__(other)

  def __eq__(self, other):
    return self.__cmp__(other) == 0

  def __cmp__(self, other):
    if type(other) != type(self):
      raise TypeError("Incompatible comparison type")
    return cmp(self._cols, other._cols) or cmp(self._row, other._row)

  def __hasattr__(self, this):
    if this in self._cols:
      return self._cols.index(this) < len(self._row)
    return False

  __contains__ = __hasattr__

  def get(self, this, default=None):
    if (this in self._cols) and (self._cols.index(this) < len(self._row)):
      return self._row[self._cols.index(this)]
    return default

  def __getattr__(self, this):
    try:
      return self._row[self._cols.index(this)]
    except:
      raise AttributeError, this

  def __getitem__(self, this):
    return self._row[self._cols.index(this)]

  def __str__(self):
    return "Row(" + ','.join(map(_fmt, zip(self._cols, self._row))) + ")"


class Rowset(object):
  # Rowsets are collections of Row objects.
  #
  # Rowsets support most of the list interface:
  #   iteration, indexing and slicing
  #
  # As well as the following methods: 
  #
  #   IndexedBy(column)
  #     Returns an IndexRowset keyed on given column. Requires the column to
  #     be usable as primary key.
  #
  #   GroupedBy(column)
  #     Returns a FilterRowset keyed on given column. FilterRowset objects
  #     can be accessed like dicts. See FilterRowset class below.
  #
  #   SortBy(column, reverse=True)
  #     Sorts rowset in-place on given column. for a descending sort,
  #     specify reversed=True.
  #
  #   SortedBy(column, reverse=True)
  #     Same as SortBy, except this returns a new rowset object instead of
  #     sorting in-place.
  #
  #   Select(columns, row=False)
  #     Yields a column values tuple (value, ...) for each row in the rowset.
  #     If only one column is requested, then just the column value is
  #     provided instead of the values tuple.
  #     When row=True, each result will be decorated with the entire row.
  #

  def IndexedBy(self, column):
    return IndexRowset(self._cols, self._rows, column)

  def GroupedBy(self, column):
    return FilterRowset(self._cols, self._rows, column)

  def SortBy(self, column, reverse=False):
    ix = self._cols.index(column)
    self.sort(key=lambda e: e[ix], reverse=reverse)

  def SortedBy(self, column, reverse=False):
    rs = self[:]
    rs.SortBy(column, reverse)
    return rs

  def Select(self, *columns, **options):
    if len(columns) == 1:
      i = self._cols.index(columns[0])
      if options.get("row", False):
        for line in self._rows:
          yield (line, line[i])
      else:
        for line in self._rows:
          yield line[i]
    else:
      i = map(self._cols.index, columns)
      if options.get("row", False):
        for line in self._rows:
          yield line, [line[x] for x in i]
      else:
        for line in self._rows:
          yield [line[x] for x in i]


  # -------------

  def __init__(self, cols=None, rows=None):
    self._cols = cols or []
    self._rows = rows or []

  def append(self, row):
    if isinstance(row, list):
      self._rows.append(row)
    elif isinstance(row, Row) and len(row._cols) == len(self._cols):
      self._rows.append(row._row)
    else:
      raise TypeError("incompatible row type")

  def __add__(self, other):
    if isinstance(other, Rowset):
      if len(other._cols) == len(self._cols):
        self._rows += other._rows
    raise TypeError("rowset instance expected")

  def __nonzero__(self):
    return not not self._rows

  def __len__(self):
    return len(self._rows)

  def copy(self):
    return self[:]

  def __getitem__(self, ix):
    if type(ix) is slice:
      return Rowset(self._cols, self._rows[ix])
    return Row(self._cols, self._rows[ix])

  def sort(self, *args, **kw):
    self._rows.sort(*args, **kw)

  def __str__(self):
    return ("Rowset(columns=[%s], rows=%d)" % (','.join(self._cols), len(self)))

  def __getstate__(self):
    return (self._cols, self._rows)

  def __setstate__(self, state):
    self._cols, self._rows = state



class IndexRowset(Rowset):
  # An IndexRowset is a Rowset that keeps an index on a column.
  #
  # The interface is the same as Rowset, but provides an additional method:
  #
  #   Get(key [, default])
  #     Returns the Row mapped to provided key in the index. If there is no
  #     such key in the index, KeyError is raised unless a default value was
  #     specified.
  #

  def Get(self, key, *default):
    row = self._items.get(key, None)
    if row is None:
      if default:
        return default[0]
      raise KeyError, key
    return Row(self._cols, row)

  # -------------

  def __init__(self, cols=None, rows=None, key=None):
    try:
      if "," in key:
        self._ki = ki = [cols.index(k) for k in key.split(",")]
        self.composite = True
      else:
        self._ki = ki = cols.index(key)
        self.composite = False
    except IndexError:
      raise ValueError("Rowset has no column %s" % key)

    Rowset.__init__(self, cols, rows)
    self._key = key

    if self.composite:
      self._items = dict((tuple([row[k] for k in ki]), row) for row in self._rows)
    else:
      self._items = dict((row[ki], row) for row in self._rows)

  def __getitem__(self, ix):
    if type(ix) is slice:
      return IndexRowset(self._cols, self._rows[ix], self._key)
    return Rowset.__getitem__(self, ix)

  def append(self, row):
    Rowset.append(self, row)
    if self.composite:
      self._items[tuple([row[k] for k in self._ki])] = row
    else:
      self._items[row[self._ki]] = row

  def __getstate__(self):
    return (Rowset.__getstate__(self), self._items, self._ki)

  def __setstate__(self, state):
    state, self._items, self._ki = state
    Rowset.__setstate__(self, state)


class FilterRowset(object):
  # A FilterRowset works much like an IndexRowset, with the following
  # differences:
  # - FilterRowsets are accessed much like dicts
  # - Each key maps to a Rowset, containing only the rows where the value
  #   of the column this FilterRowset was made on matches the key.

  def __init__(self, cols=None, rows=None, key=None, key2=None, dict=None):
    if dict is not None:
      self._items = items = dict
    elif cols is not None:
      self._items = items = {}

      idfield = cols.index(key)
      if not key2:
        for row in rows:
          id = row[idfield]
          if id in items:
            items[id].append(row)
          else:
            items[id] = [row]
      else:
        idfield2 = cols.index(key2)
        for row in rows:
          id = row[idfield]
          if id in items:
            items[id][row[idfield2]] = row
          else:
            items[id] = {row[idfield2]:row}

    self._cols = cols
    self.key = key
    self.key2 = key2
    self._bind()

  def _bind(self):
    items = self._items
    self.keys = items.keys
    self.iterkeys = items.iterkeys
    self.__contains__ = items.__contains__
    self.has_key = items.has_key
    self.__len__ = items.__len__
    self.__iter__ = items.__iter__

  def copy(self):
    return FilterRowset(self._cols[:], None, self.key, self.key2, dict=copy.deepcopy(self._items))

  def get(self, key, default=_unspecified):
    try:
      return self[key]
    except KeyError:
      if default is _unspecified:
        raise
    return default

  def __getitem__(self, i):
    if self.key2:
      return IndexRowset(self._cols, None, self.key2, self._items.get(i, {}))
    return Rowset(self._cols, self._items[i])

  def __getstate__(self):
    return (self._cols, self._rows, self._items, self.key, self.key2)

  def __setstate__(self, state):
    self._cols, self._rows, self._items, self.key, self.key2 = state
    self._bind()



  



##########################################################################
#This class is engineered as a handler for BaseHTTPRequest,
#it catches the authentication token after login.
#the original (and mostly unmodified) template from this 
#comes from CREST-market-downloader from fuzzworks.
#note: i think this class inherits from BaseHTTPServer.BaseHTTPRequestHandler
class CodeHandler(BaseHTTPRequestHandler):
  """retrieve authentication token from localhost redirect after login"""
  def do_GET(self):
    if self.path == "/favicon.ico":
      return;
    parsed_path = urlparse.urlparse(self.path)
    parts=urlparse.parse_qs(parsed_path.query)
    self.send_response(200)
    self.end_headers()
    self.wfile.write('Login successful. you can close this window now')
    pubsub.publish('code', str(parts['code'][0]))
    self.finish()
    self.connection.close()    
  def log_message(self, format, *args):
    return


