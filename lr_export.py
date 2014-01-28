import ConfigParser, datetime, hashlib, json, logging, LRSignature, os, sys, traceback, urllib, urllib2, base64
from xml.sax.saxutils import escape
APP_NAME="lr_export"
LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %I:%M:%S %p"
LOG_FILENAME_FORMAT = APP_NAME + "-%Y%m%d%H%M%S" + '.log'
API_DATE = '%m%d%Y'
SHORT_DATE = "%Y-%m-%d"
LANGUAGE_CODES = {'English US':'eng', 'Spanish':'spa', 'Bulgarian':'bul', 'Arabic':'ara', 'Afrikaans':'afr', 'Cantonese':'yue', 'Chinese':'chi', 'Czech':'ces', 'Danish':'dan', 'Dutch':'dut', 'French':'fre', 'German':'ger', 'Gujarati':'guj', 'Hebrew':'heb', 'Hindi':'hin', 'Italian':'ita', 'Japanese':'jpn', 'Malayalam':'mal', 'Mandarin':'cmn', 'Marathi':'mar', 'Panjabi':'pan', 'Russian':'rus', 'Swedish':'sve', 'Tamil':'tam', 'Telugu':'tel', 'Turkish':'tur', 'Latin':'lat', 'Bengali':'ben', 'Portuguese':'por', 'Javanese':'jav', 'Korean':'kor', 'Vietnamese':'vie', 'Urdu':'urd', 'English Great Britain':'eng'}
CATEGORIES = ['Educational Materials', 'Textbooks']

def readConfig():
    config = ConfigParser.SafeConfigParser()
    config.read(APP_NAME + ".conf")
    return config

def initLogging(config):
    logName = datetime.datetime.today().strftime(LOG_FILENAME_FORMAT)
    logPath = os.path.realpath(config.get('Main', 'log_path'))
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, filename=os.path.join(logPath, logName), filemode='w', level=logging.INFO)
    logging.info("Job started.")

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

            retry = 0
            searchResponse = None

            url = search_url % (api_host, urllib.quote(category), startDate.strftime(API_DATE), page, safe_username, api_key)
            logUrl=url.split("?")[0] #don't log the api key, so remove everything after the question mark
            logging.info("Retrieving booklist of books since " + startDate.strftime(SHORT_DATE) + " from " + logUrl)
            req=urllib2.Request(url, headers=password_header)

            while (searchResponse == None and retry < 3):
                try:
                    conn = urllib2.urlopen(req)
                    res=conn.read()
                    conn.close()

                    #pythonize json gotten from reading the url response
                    searchResponse=json.loads(res) 
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

                            # fetch data
                            tempResult = fetchBookData(req)
                            # store only if we got one
                            if tempResult != None:
                                tempResult["locator"]="http://www.bookshare.org/browse/book/"+str(bookId)
                                result[bookId] = tempResult

                    logging.info("Finished fetching page %d of %d." % (page, numPages))

                    # set to next page
                    # if page < numPages:
                    if page < 1:
                        page = page + 1
                    else:
                        page = 0

                except ValueError:
                    print "JSON failure"
                    res = None
                    retry = retry + 1
                except KeyError:
                    print "JSON failure"
                    res = None
                    retry = retry + 1
                except urllib2.HTTPError as httpError:
                    logging.info("Bookshare API responded with " + str(httpError.code) + " " + httpError.msg + ". Going to retry.")
                    httpError.close()
                    retry = retry + 1
    return result

def fetchBookData(req):
    bookResponse = None
    retry = 0
    while bookResponse == None and retry < 3:
        try:
            conn = urllib2.urlopen(req)
            bookResponse=json.loads(conn.read())
            conn.close()
            data=bookResponse["bookshare"]["book"]["metadata"]
            logging.info("book data:\n"+str(data))
            logging.info("Making envelopes from this book's metadata. Categories: "+str(data["category"]))
            return data
        except urllib2.HTTPError as httpError :
            logging.info("API Server responded with " + str(httpError.code) + " " + httpError.msg + ". Going to retry.")
            httpError.close()
            retry = retry + 1
        except ValueError:
            print "JSON failure"
            res = None
            retry = retry + 1
        except KeyError:
            print "JSON failure"
            res = None
            retry = retry + 1
    return None

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
        logging.info(json.dumps(makeEnvelope(bookId, books[bookId], signer)))
        documents.append(makeEnvelope(bookId, books[bookId], signer))
        
    #JSON-ify results
    doc_json=json.dumps(doc)
    
    numBooks = len(documents)
    if numBooks > 0:
        publishUrl = "http://" + config.get('Learning Registry', 'lr_node') + "/publish"
        username = config.get('Learning Registry', 'lr_username')
        password = config.get('Learning Registry', 'lr_password')
        publishRequest=urllib2.Request(publishUrl, headers={"Content-type": "application/json; charset=utf-8", "Authorization" : "Basic " + base64.b64encode(username + ":" + password)})

        retry = 0
        successes=0
        publishResponse = None
        while ((publishResponse == None) and retry < 3):
            logging.info("Publishing data to LR node at " + publishUrl + ", attempt " + str(retry + 1))
            try:
                conn = urllib2.urlopen(publishRequest, data=doc_json)
                publishResponse = json.loads(conn.read())
                conn.close()
                if publishResponse["OK"] == False:
                    logging.info("Publish failed, retrying")
                    publishResponse = None
                    retry = retry + 1
                else:
                    for result in publishResponse["document_results"]:
                        if not result["OK"]:
                            logging.error("Error in envelope: " + str(result["error"]))
                        else:
                            logging.info("Published document " + result["doc_ID"])
                            successes+=1
            except urllib2.HTTPError as httpError:
                logging.info("LR Node responded with " + str(httpError.code) + " " + httpError.msg + ". Going to retry.")
                httpError.close()
                retry = retry + 1
            except ValueError:
                logging.info("Bad JSON response on publish attempt. Retrying.")
                httpError.close()
                retry = retry + 1
        logging.info("Job completed, Found "+str(numBooks)+" books to upload. Uploaded "+str(successes)+" of "+str(numBooks)+" records successfully.")
    else:
        logging.info("No envelopes created, nothing to upload. Job completed.")

def makeEnvelope(bookId, data, signer):
    payload=mapper_jsonLD(bookId, data)
    #json of envelope to be written, in python form; each book goes into one of these:
    envelope={
        "doc_type": "resource_data", 
        "doc_version": "0.49.0",
        "active": True,
        "TOS": {"submission_TOS": "http://www.learningregistry.org/tos/cc0/v0-5/"},
        "identity": {
            "submitter": "Bookshare.org",
            "signer": "Bookshare.org",
            "submitter_type": "agent"
        },
        "resource_locator": data["locator"],
        "keys": ["accessible", "daisy", "bookshare"],
        "resource_data_type": "metadata",
        "payload_placement": "inline",
        "payload_schema": ["json", "json-ld", "schema.org", "lrmi"],
        "resource_data": payload
    }

    #add info to keys list:
    for cat in data["category"]: envelope["keys"].append(cat)

    # sign envelope
    signer.sign(envelope)
    return envelope

def mapper_jsonLD(bookId, data):
    #maps Bookshare json data ("data") to JSON-LD

    payload = {
        "@context": {
            "@vocab": "http://schema.org/",
            "lrmi": "http://lrmi.net/the-specification#",
            "useRightsUrl": {
                "@id": "lrmi:useRightsUrl",
                "@type": "@id"
            }
        },
        "@type" : "http://schema.org/Book",
        "@id": data["locator"],
        "url": data["locator"],
        "name": data["title"],
        "bookFormat": "EBook/DAISY3",
        "useRightsUrl": "http://www.bookshare.org/_/aboutUs/legalInformation",
        "provider": {
            "@type": "http://schema.org/Organization",
            "name": "Bookshare.org"
        },
        "interactivityType": "expositive",
        "learningResourceType": "textbook",
        "audience": {
            "@type": "http://schema.org/EducationalAudience",
            "educationalRole": "student"
        },
        "accessibilityFeature": [
            "displayTransformability/font-size",
            "displayTransformability/font-family",
            "displayTransformability/color",
            "displayTransformability/background-color",
            "bookmarks",
            "readingOrder",
            "structuralNavigation"
        ],
        "accessibilityHazard": [
            "noFlashingHazard",
            "noMotionSimulationHazard",
            "noSoundHazard"
        ],
        "accessibilityControl": [
            "fullKeyboardControl",
            "fullMouseControl"
        ]
    }

    # authors
    if data.has_key("author") and len(data["author"]) > 0:
        payload["author"] = data["author"]

    if data.has_key("category") and len(data["category"]) > 0:
        payload["keywords"] = data["category"]

    if data.has_key("language") and len(data["language"]) > 0:
        languages = []
        for lang in data["language"]:
            languages.append(LANGUAGE_CODES[lang])
        payload["inLanguage"] = languages

    if data.has_key("completeSynopsis") and len(data["completeSynopsis"].strip()) > 0:
        payload["description"] = data["completeSynopsis"].strip()
    elif data.has_key("briefSynopsis") and len(data["briefSynopsis"].strip()) > 0:
        payload["description"] = data["briefSynopsis"].strip()

    if data.has_key("isbn13"):
        payload["isbn"] = data["isbn13"]

    if data.has_key("publisher"):
        payload["publisher"] = {
            "@type": "http://schema.org/Organization",
            "name": data["publisher"]
        }

    if data.has_key("publish_date"):
        payload["datePublished"] = data["datePublished"].strftime(SHORT_DATE)
        
    if data.has_key("copyright"):
        payload["copyrightYear"] = data["copyright"]

    return payload

if __name__ == "__main__":
    config = readConfig()
    lastRunDate = getLastRunDate(config)
    initLogging(config)
    print("Searching for new books since %s..." % (lastRunDate.strftime(LOG_DATE_FORMAT),))
    books = fetchBooks(config, lastRunDate)
    print("Found data for %d books" % (len(books),))

    # do in batches
    batchSize = int(config.get('Main', 'publish_batch_size'))
    bookBatch = {}
    for bookId in books.keys():
        bookBatch[bookId] = books[bookId]
        if (len(bookBatch) == batchSize):
            pushMetadata(config, bookBatch)
            bookBatch = {}
    
    # push any leftovers
    pushMetadata(config, bookBatch)

    print("Done.")

