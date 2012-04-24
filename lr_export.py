import ConfigParser, datetime, hashlib, json, logging, LRSignature, os, sys, traceback, urllib, urllib2
from xml.sax.saxutils import escape
APP_NAME="lr_export"
LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %I:%M:%S %p"
LOG_FILENAME_FORMAT = APP_NAME + "-%Y%m%d%H%M%S" + '.log'
API_DATE = '%m%d%Y'
SHORT_DATE = "%Y-%m-%d"
LANGUAGE_CODES = {'English US':'eng', 'Spanish':'spa', 'Bulgarian':'bul', 'Arabic':'ara', 'Afrikaans':'afr', 'Cantonese':'yue', 'Chinese':'chi', 'Czech':'ces', 'Danish':'dan', 'Dutch':'dut', 'French':'fre', 'German':'ger', 'Gujarati':'guj', 'Hebrew':'heb', 'Hindi':'hin', 'Italian':'ita', 'Japanese':'jpn', 'Malayalam':'mal', 'Mandarin':'cmn', 'Marathi':'mar', 'Panjabi':'pan', 'Russian':'rus', 'Swedish':'sve', 'Tamil':'tam', 'Telugu':'tel', 'Turkish':'tur', 'Latin':'lat', 'Bengali':'ben', 'Portuguese':'por', 'Javanese':'jav', 'Korean':'kor', 'Vietnamese':'vie', 'Urdu':'urd', 'English Great Britain':'eng'}
CATEGORIES = ['Educational Materials', 'Textbooks']
BOOKSHARE_FORMATS = {"Daisy":{"description":"ANSI/NISO Z39.86-2005", "accessMode":"allTextual"}, "BRF":{"description":"Braille-Ready Format", "accessMode":"brailleOnly"}}

def readConfig():
    config = ConfigParser.SafeConfigParser()
    config.read(APP_NAME + ".conf")
    return config

def initLogging(config):
    logName = datetime.datetime.today().strftime(LOG_FILENAME_FORMAT)
    logPath = os.path.realpath(config.get('Main', 'log_path'))
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, filename=os.path.join(logPath, logName), filemode='w', level=logging.INFO)
    logging.info("Job started.")
    sys.excepthook=exceptionHandler

def getLastRunDate(config):
    logFiles = os.listdir(os.path.realpath(config.get('Main', 'log_path')))
    try:
        if len(logFiles) > 0:
            logFiles.sort()
            return datetime.datetime.strptime(logFiles[-1], LOG_FILENAME_FORMAT)
    except:
        pass
    
    # sensible default
    return datetime.datetime(2002, 01, 01)

def fetchBooks(config, startDate):
    # prepare all the bits!
    safe_username=urllib.quote_plus(config.get('Bookshare', 'username'), safe='/') #take care of spaces and special chars
    password_hash=urllib.quote(hashlib.md5(config.get('Bookshare', 'password')).hexdigest())
    password_header={"X-password":password_hash}
    api_key = config.get('Bookshare', 'api_key')
    api_host = config.get('Bookshare', 'api_host')
    
    result = {}
    
    search_url = "https://%s/book/search/category/%s/since/%s/limit/250/page/%d/format/json/for/%s?api_key=%s"
    detail_url = "https://%s/book/id/%d/format/json/for/%s?api_key=%s"
    
    for category in CATEGORIES:
        page = 1
        while page > 0:
            url = search_url % (api_host, urllib.quote(category), startDate.strftime(API_DATE), page, safe_username, api_key)
            logUrl=url.split("?")[0] #don't log the api key, so remove everything after the question mark
            logging.info("Retrieving booklist of books since " + startDate.strftime(SHORT_DATE) + " from " + logUrl)
            req=urllib2.Request(url, headers=password_header)
            conn = urllib2.urlopen(req)
            res=conn.read()
            conn.close()
            searchResponse=json.loads(res) #pythonize json gotten from reading the url response
            if containsErrors(searchResponse): #no point in continuing, so exit
                sys.exit(0)
            root=searchResponse["bookshare"]
            numPages = int(root["book"]["list"]["numPages"])
            #for every book in the booklist, request its metadata using its id:
            for book in root["book"]["list"]["result"]:
                bookId=book['id']
                
                if (result.has_key(bookId) == True):
                    logging.info("Title \"" + book["title"] + "\" already exists in result set. Skipping metadata fetch.")
                else:
                    url=detail_url % (api_host, bookId, safe_username, api_key)
                    logUrl=url.split("?")[0]
                    logging.info("Retrieving metadata for \""+book["title"]+"\" with url "+logUrl)
                    req=urllib2.Request(url, headers=password_header)
                    conn = urllib2.urlopen(req)
                    bookResponse=json.loads(conn.read())
                    conn.close()
                    if containsErrors(bookResponse): continue #the function will log the errors, but we won't let one book stop the whole script, so skip it
                    data=bookResponse["bookshare"]["book"]["metadata"]
                    logging.debug("book data:\n"+str(data))
                    logging.info("Making envelopes from this book's metadata. Categories: "+str(data["category"]))
                    data["locator"]="http://www.bookshare.org/browse/book/"+str(bookId)
                    result[bookId]=data
            logging.info("Finished fetching page %d of %d." % (page, numPages))
            if page < numPages:
                page = page + 1
            else:
                page = 0
    return result

def getSigner(config):
    fingerprint = config.get('GPG', 'key_fingerprint')
    passPhrase = config.get('GPG', 'key_passphrase')
    keyLocations = [config.get('GPG', 'public_key_url'),]
    gpgBin = config.get('GPG', 'path')
    return LRSignature.sign.Sign.Sign_0_21(privateKeyID=fingerprint, passphrase=passPhrase, publicKeyLocations=keyLocations, gpgbin=gpgBin)

def pushMetadata(config, books):
    signer = getSigner(config)
    documents = []
    doc = {"documents": documents}
    for bookId in books.keys():
        documents.append(makeEnvelope(bookId, books[bookId], signer))
        
    #JSON-ify results
    doc_json=json.dumps(doc)
    
    numBooks = len(documents)
    if numBooks > 0:
        publishUrl = "http://" + config.get('Learning Registry', 'lr_node') + "/publish"
        publishRequest=urllib2.Request(publishUrl, headers={"Content-type": "application/json; charset=utf-8"})
        logging.info("Publishing data to LR node at "+publishUrl)
        res=json.loads(urllib2.urlopen(publishRequest, data=doc_json).read())
        #now check "res" to make sure everything went okay:
        successes=0
        for i, result in enumerate(res["document_results"]):
           if containsErrors(res, i):
                continue
           successes+=1
        logging.info("Job completed, Found "+str(numBooks)+" books to upload. Uploaded "+str(successes)+" of "+str(numBooks)+" records successfully.")
    else:
        logging.info("No envelopes created, nothing to upload. Job completed.")

def makeEnvelope(bookId, data, signer):
    payload=mapper_dublinCore(bookId, data)
    #json of envelope to be written, in python form; each book goes into one of these:
    envelope={
        "doc_type": "resource_data", 
        "doc_version": "0.23.0",  #how do we determine this?
        "resource_data_type": "metadata",
        "active": True,
        "TOS": {"submission_TOS": "http://www.learningregistry.org/tos/cc-by-3-0/v0-5/"},
        "identity": {
            "curator": "",
            "owner": "",
            "submitter": "Bookshare.org",
            "signer": "Bookshare.org",
            "submitter_type": "agent"
        },
        "resource_locator": data["locator"],
        "keys": ["Accessible", "AIM"],
        "payload_placement": "inline",
        "payload_schema": ["NSDL DC 1.02.020",],
        "payload_schema_locator": "http://ns.nsdl.org/schemas/nsdl_dc/nsdl_dc_v1.02.xsd",
        "resource_data": payload
    }
    #add info to keys list:
    for cat in data["category"]: envelope["keys"].append(cat)
    for format in data["downloadFormat"]:
        if format in BOOKSHARE_FORMATS.keys():
            envelope["keys"].append(format)
            envelope["keys"].append(BOOKSHARE_FORMATS[format]["description"])
    signer.sign(envelope)
    return envelope

def mapper_dublinCore(bookId, data):
    #maps Bookshare json data ("data") to DC XML
    
    s="""<?xml version="1.0"?>
<nsdl_dc:nsdl_dc xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:dc="http://purl.org/dc/elements/1.1/"
        xmlns:dct="http://purl.org/dc/terms/"
        xmlns:ieee="http://www.ieee.org/xsd/LOMv1p0"
        xmlns:nsdl_dc="http://ns.nsdl.org/nsdl_dc_v1.02/"
        schemaVersion="1.02.020"
        xsi:schemaLocation="http://ns.nsdl.org/nsdl_dc_v1.02/ http://ns.nsdl.org/schemas/nsdl_dc/nsdl_dc_v1.02.xsd">
"""
    s+='    <dc:identifier xsi:type="dct:URI">http://www.bookshare.org/browse/book/%d</dc:identifier>\n' % (bookId,)
    s+='    <dc:title>%s</dc:title>\n' % (escape(data['title']),)
    for author in data["author"]:
        s+='    <dc:creator>%s</dc:creator>\n' % (escape(author),)
    if data.has_key("completeSynopsis"):
        synopsis = data["completeSynopsis"]
    elif data.has_key("briefSynopsis"):
        synopsis=data["briefSynopsis"]
    else:
        synopsis=""
    s+='    <dc:description>%s</dc:description>\n' % (escape(synopsis),)
    s+='    <dc:publisher>%s</dc:publisher>\n' % (escape(data['publisher']),)
    s+='    <dc:date>%s</dc:date>\n' % (data['copyright'],)
    s+='    <dct:dateCopyrighted>%s</dct:dateCopyrighted>\n' % (data['copyright'],)
    for l in data["language"]:
        try:
            s+='    <dc:language>%s</dc:language>\n' % (LANGUAGE_CODES[l],)
        except KeyError:
            logger.warn("The language '"+l+"' was not found in the list of known languages; this language will not be included in this book's envelope.")
        continue
    for category in data["category"]:
        s+='    <dc:subject>%s</dc:subject>\n' % (escape(category),)
    s+='    <dc:type xsi:type="dct:DCMIType">Text</dc:type>\n'
    s+='    <dc:type xsi:type="nsdl_dc:NSDLType">Instructional Material</dc:type>\n'
    for cat in data["category"]:
        if cat.lower()=="textbooks": s+='    <dc:type xsi:type="nsdl_dc:NSDLType">Textbook</dc:type>\n'
    for format in data["downloadFormat"]:
        if format in BOOKSHARE_FORMATS.keys():
            s+='    <dc:format>%s</dc:format>\n' % (format.lower(),)
            s+='    <dc:format>%s</dc:format>\n' % (BOOKSHARE_FORMATS[format]["description"],)
    if data.has_key('isbn13'):
        s+='    <dct:isFormatOf xsi:type="dct:URI">urn:isbn:%s</dct:isFormatOf>\n' % (data['isbn13'],)
    s+='    <dct:accessRights xsi:type="nsdl_dc:NSDLAccess">'
    if data["freelyAvailable"]:
        s+='Free access'
    elif not data["freelyAvailable"]:
        s+='Available by subscription'
    s+='</dct:accessRights>\n'
    s+='    <dc:rights>http://www.bookshare.org/_/aboutUs/legalInformation</dc:rights>\n'
    for format in data["downloadFormat"]:
        if format in BOOKSHARE_FORMATS.keys():
            s+='    <dct:accessibility>%s</dct:accessibility>\n' % (BOOKSHARE_FORMATS[format]["accessMode"],)
    s+='</nsdl_dc:nsdl_dc>'
    return s

def containsErrors(res, mode="bs", i=0):
    #mode=="bs": check for Bookshare errors; else check for LR errors
    #"i" is for LR only since each result is an element of a list and may be ok or not
    if mode=="bs".lower():
        root=res["bookshare"]
        if "statusCode" in root.keys():
            logging.error("Error retrieving latest booklist: "+root["messages"][0]+" (code "+str(root["statusCode"])+")")
            return True
    else: #LR errors
        result=res["document_results"][i]
        if not result["OK"]:
            logging.error("Error in envelope: "+str(result["error"]))
            return True
    return False #no errors found

def exceptionHandler(type, value, tb):
    #used to override default exceptions so we can log them, even if we don't catch them
    exc=traceback.format_exception(type, value, tb)
    err="Uncaught Exception:\n"
    err+="".join(line for line in exc)
    logging.error(err)

if __name__ == "__main__":
    config = readConfig()
    lastRunDate = getLastRunDate(config)
    initLogging(config)
    print("Searching for new books since %s..." % (lastRunDate.strftime(LOG_DATE_FORMAT),))
    books = fetchBooks(config, lastRunDate)
    print("Found data for %d books" % (len(books),))
    pushMetadata(config, books)
    print("Done.")

