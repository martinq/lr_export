'''
Copyright 2011 SRI International

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Created on May 6, 2011

@author: jklo
'''
import unittest, json, calendar, time, os, logging
from gnupg import GPG
from LRSignature.sign.Sign import Sign_0_21
from LRSignature.errors import UnknownKeyException
import types
import sys

log =  logging.getLogger(__name__)

class Test(unittest.TestCase):
    '''Unit test cases for signing envelopes from the Learning Registry'''
    def __init__(self, methodName="runTest"):
        
        self.gpgbin="/usr/local/bin/gpg"
        self.gnupgHome = os.path.expanduser(os.path.join("~", ".gnupg"))
        self.gpg = GPG(gpgbinary=self.gpgbin, gnupghome=self.gnupgHome)
        
        unittest.TestCase.__init__(self, methodName)
        
        self.testDataDir = None
        configFile = os.path.join("config.cfg")
        if os.path.exists(configFile):
            config = json.load(file(configFile))
            
            if config.has_key("global"):
                if config["global"].has_key("testdata") and os.path.exists(config["global"]["testdata"]):
                    self.testDataDir = config["global"]["testdata"]
        
        
        
    def setUp(self):
        now = time.localtime()
        now = calendar.timegm(now)
        self.goodEmail = "signTest-{0}@learningregistry.org".format(now)
        self.goodRealName = "Autogenerated Sign Test"
        self.goodpassphrase = "supersecret"
        
        input = self.gpg.gen_key_input(name_real=self.goodRealName, name_email=self.goodEmail, passphrase=self.goodpassphrase)
        self.goodPrivateKey = self.gpg.gen_key(input)
        
        privateKeyAvailable = False
        privateKeys = self.gpg.list_keys(secret=True)
        for skey in privateKeys:
            if skey["keyid"] == self.goodPrivateKey.fingerprint:
                privateKeyAvailable = True
                self.privateKeyInfo = skey
                break
            if skey["fingerprint"] == self.goodPrivateKey.fingerprint:
                privateKeyAvailable = True
                self.privateKeyInfo = skey
                break
        
        assert privateKeyAvailable == True, "Could not locate generated Private Key"
        
        self.goodkeyid = self.privateKeyInfo["keyid"]
        
        self.goodowner = self.privateKeyInfo["uids"][0]
        
        
        self.badkeyid = "XXXXXXXXXXXXXXXX"
        self.badpassphrase = "bad passphrase"
        
        self.sampleJSON = '''
            {
                "_id":"00e3f67232e743b6bc2a079bd98ff55a",
                "_rev":"1-8163d32f6cc9996f2b7228d8b5db7962",
                "doc_type":"resource_data",
                "update_timestamp":"2011-03-14 13:36:04.617999",
                "resource_data":"<oai_dc:dc xmlns:oai_dc=\\"http://www.openarchives.org/OAI/2.0/oai_dc/\\" xmlns:dc=\\"http://purl.org/dc/elements/1.1/\\" xmlns:xsi=\\"http://www.w3.org/2001/XMLSchema-instance\\" xmlns=\\"http://www.openarchives.org/OAI/2.0/\\" xsi:schemaLocation=\\"http://www.openarchives.org/OAI/2.0/oai_dc/                          http://www.openarchives.org/OAI/2.0/oai_dc.xsd\\">\\n<dc:title>A chat about America. October and November, 1884.</dc:title>\\n<dc:creator>J. P.</dc:creator>\\n<dc:subject>United States--Description and travel.</dc:subject>\\n<dc:description>\\"Printed for private circulation only.\\"</dc:description>\\n<dc:description>Electronic reproduction. Washington, D.C. : Library of Congress, [2002-2003]</dc:description>\\n<dc:publisher>Manchester, Palmer &amp; Howe</dc:publisher>\\n<dc:date>1885</dc:date>\\n<dc:type>text</dc:type>\\n<dc:identifier>http://hdl.loc.gov/loc.gdc/lhbtn.12281</dc:identifier>\\n<dc:language>eng</dc:language>\\n<dc:coverage>United States</dc:coverage>\\n</oai_dc:dc>\\n      ",
                "keys":["United States--Description and travel.","eng"],
                "submitter_type":"agent",
                "resource_data_type":"metadata",
                "payload_schema_locator":"http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
                "payload_placement":"inline",
                "submitter":"NSDL 2 LR Data Pump",
                "payload_schema":["oai_dc"],
                "node_timestamp":"2011-03-14 13:36:04.617999",
                "doc_version":"0.10.0",
                "create_timestamp":"2011-03-14 13:36:04.617999",
                "active":true,
                "publishing_node":"string",
                "resource_locator":"http://hdl.loc.gov/loc.gdc/lhbtn.12281",
                "doc_ID":"00e3f67232e743b6bc2a079bd98ff55a",
                "TOS": {
                    "submission_TOS": "http://example.com/tos/unknown",
                    "submission_attribution": "unidentified"
                }
            }
            '''
        
        self.sampleJSON_strip = '''{"keys": ["United States--Description and travel.", "eng"], "TOS": {"submission_attribution": "unidentified", "submission_TOS": "http://example.com/tos/unknown"}, "payload_placement": "inline", "active": true, "resource_locator": "http://hdl.loc.gov/loc.gdc/lhbtn.12281", "doc_type": "resource_data", "resource_data": "<oai_dc:dc xmlns:oai_dc=\\"http://www.openarchives.org/OAI/2.0/oai_dc/\\" xmlns:dc=\\"http://purl.org/dc/elements/1.1/\\" xmlns:xsi=\\"http://www.w3.org/2001/XMLSchema-instance\\" xmlns=\\"http://www.openarchives.org/OAI/2.0/\\" xsi:schemaLocation=\\"http://www.openarchives.org/OAI/2.0/oai_dc/                          http://www.openarchives.org/OAI/2.0/oai_dc.xsd\\">\\n<dc:title>A chat about America. October and November, 1884.</dc:title>\\n<dc:creator>J. P.</dc:creator>\\n<dc:subject>United States--Description and travel.</dc:subject>\\n<dc:description>\\"Printed for private circulation only.\\"</dc:description>\\n<dc:description>Electronic reproduction. Washington, D.C. : Library of Congress, [2002-2003]</dc:description>\\n<dc:publisher>Manchester, Palmer &amp; Howe</dc:publisher>\\n<dc:date>1885</dc:date>\\n<dc:type>text</dc:type>\\n<dc:identifier>http://hdl.loc.gov/loc.gdc/lhbtn.12281</dc:identifier>\\n<dc:language>eng</dc:language>\\n<dc:coverage>United States</dc:coverage>\\n</oai_dc:dc>\\n      ", "submitter_type": "agent", "resource_data_type": "metadata", "payload_schema_locator": "http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd", "payload_schema": ["oai_dc"], "doc_version": "0.10.0", "submitter": "NSDL 2 LR Data Pump"}'''
        self.sampleJSON_strip_normal = '''{"keys": ["United States--Description and travel.", "eng"], "TOS": {"submission_attribution": "unidentified", "submission_TOS": "http://example.com/tos/unknown"}, "payload_placement": "inline", "active": "true", "resource_locator": "http://hdl.loc.gov/loc.gdc/lhbtn.12281", "doc_type": "resource_data", "resource_data": "<oai_dc:dc xmlns:oai_dc=\\"http://www.openarchives.org/OAI/2.0/oai_dc/\\" xmlns:dc=\\"http://purl.org/dc/elements/1.1/\\" xmlns:xsi=\\"http://www.w3.org/2001/XMLSchema-instance\\" xmlns=\\"http://www.openarchives.org/OAI/2.0/\\" xsi:schemaLocation=\\"http://www.openarchives.org/OAI/2.0/oai_dc/                          http://www.openarchives.org/OAI/2.0/oai_dc.xsd\\">\\n<dc:title>A chat about America. October and November, 1884.</dc:title>\\n<dc:creator>J. P.</dc:creator>\\n<dc:subject>United States--Description and travel.</dc:subject>\\n<dc:description>\\"Printed for private circulation only.\\"</dc:description>\\n<dc:description>Electronic reproduction. Washington, D.C. : Library of Congress, [2002-2003]</dc:description>\\n<dc:publisher>Manchester, Palmer &amp; Howe</dc:publisher>\\n<dc:date>1885</dc:date>\\n<dc:type>text</dc:type>\\n<dc:identifier>http://hdl.loc.gov/loc.gdc/lhbtn.12281</dc:identifier>\\n<dc:language>eng</dc:language>\\n<dc:coverage>United States</dc:coverage>\\n</oai_dc:dc>\\n      ", "submitter_type": "agent", "resource_data_type": "metadata", "payload_schema_locator": "http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd", "payload_schema": ["oai_dc"], "doc_version": "0.10.0", "submitter": "NSDL 2 LR Data Pump"}''' 
        self.sampleJSON_strip_normal_bencode = '''d3:TOSd14:submission_TOS30:http://example.com/tos/unknown22:submission_attribution12:unidentifiede6:active4:true8:doc_type13:resource_data11:doc_version6:0.10.04:keysl38:United States--Description and travel.3:enge17:payload_placement6:inline14:payload_schemal6:oai_dce22:payload_schema_locator90:http://www.openarchives.org/OAI/2.0/oai_dc/ http://www.openarchives.org/OAI/2.0/oai_dc.xsd13:resource_data968:<oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.openarchives.org/OAI/2.0/" xsi:schemaLocation="http://www.openarchives.org/OAI/2.0/oai_dc/                          http://www.openarchives.org/OAI/2.0/oai_dc.xsd">\n<dc:title>A chat about America. October and November, 1884.</dc:title>\n<dc:creator>J. P.</dc:creator>\n<dc:subject>United States--Description and travel.</dc:subject>\n<dc:description>"Printed for private circulation only."</dc:description>\n<dc:description>Electronic reproduction. Washington, D.C. : Library of Congress, [2002-2003]</dc:description>\n<dc:publisher>Manchester, Palmer &amp; Howe</dc:publisher>\n<dc:date>1885</dc:date>\n<dc:type>text</dc:type>\n<dc:identifier>http://hdl.loc.gov/loc.gdc/lhbtn.12281</dc:identifier>\n<dc:language>eng</dc:language>\n<dc:coverage>United States</dc:coverage>\n</oai_dc:dc>\n      18:resource_data_type8:metadata16:resource_locator38:http://hdl.loc.gov/loc.gdc/lhbtn.122819:submitter19:NSDL 2 LR Data Pump14:submitter_type5:agente'''
        self.sampleJSON_sha256 = '''ef1b3b63adc663602c7a3c7595951b2761b34f5f6490ea1acee3df0fd97db03c'''
        
        self.sampleKeyLocations = [
                                   "http://example.com/mykey",
                                   "http://example2.com/mykey"
                                   ]
       
        
        self.signatureTemplate = '{{"key_location": [{0}], "key_owner": "'+self.goodowner+'", "signing_method": "LR-PGP.1.0", "signature": "{1}"}}'

    def tearDown(self):
        self.gpg.delete_keys([self.goodPrivateKey.fingerprint, ], secret=True)
        self.gpg.delete_keys([self.goodPrivateKey.fingerprint, ], secret=False)
        pass
        
    def testMissingPrivateKey(self):
        
        def missingKey():
            try:
                sign = Sign_0_21(self.badkeyid)
            except UnknownKeyException as e:
                assert e.keyid == self.badkeyid, "keyid in exception doesn't match key passed to sign."
                raise e
            
        self.assertRaises(UnknownKeyException, missingKey)

    def testPresentPrivateKey(self):
        sign = Sign_0_21(self.goodkeyid)
        assert sign.privateKeyID == self.goodkeyid 
        
    def testStrip(self):
        origJson = json.loads(self.sampleJSON)
        benchmark = json.loads(self.sampleJSON_strip)
        
        signer = Sign_0_21(self.goodkeyid)        
        stripJson = signer._stripEnvelope(origJson)
        assert benchmark == stripJson
        
    def testStripNormal(self):
        origJson = json.loads(self.sampleJSON)
        benchmark = json.loads(self.sampleJSON_strip_normal)
        
        signer = Sign_0_21(self.goodkeyid)        
        stripJson = signer._stripEnvelope(origJson)
        normalJson = signer._bnormal(stripJson)
        assert benchmark == normalJson
    
    def testStripNormalBencode(self):
        origJson = json.loads(self.sampleJSON)
        benchmark = self.sampleJSON_strip_normal_bencode
        
        signer = Sign_0_21(self.goodkeyid)        
        stripJson = signer._stripEnvelope(origJson)
        normalJson = signer._bnormal(stripJson)
        bencodeJson = signer._buildCanonicalString(normalJson)
        assert benchmark == bencodeJson
    
    def testStripNormalBencodeHash(self):
        origJson = json.loads(self.sampleJSON)
        benchmark = self.sampleJSON_sha256
        
        signer = Sign_0_21(self.goodkeyid)        
        stripJson = signer._stripEnvelope(origJson)
        normalJson = signer._bnormal(stripJson)
        bencodeJson = signer._buildCanonicalString(normalJson)
        hash = signer._hash(bencodeJson)
        assert benchmark == hash
        
    def testGetMessage(self):
        origJson = json.loads(self.sampleJSON)
        benchmark = self.sampleJSON_sha256
        
        signer = Sign_0_21(self.goodkeyid)
        message = signer.get_message(origJson)
        assert benchmark == message
    
    def testPrivateKeyOwner(self):
        benchmark = self.goodowner
        signer = Sign_0_21(self.goodkeyid)
        assert benchmark == signer._get_privatekey_owner()
    
    def testSigBlock(self):
        origJson = json.loads(self.sampleJSON)
        arbitrarySigdata = "ABCDEF0123456789-abcdef"
        arbitraryKeyLoc = self.sampleKeyLocations
        
        keyloc = ",".join(map(lambda x: '"{0}"'.format(x), arbitraryKeyLoc))
        benchmark = json.loads(self.signatureTemplate.format(keyloc, arbitrarySigdata))
        
        signer = Sign_0_21(self.goodkeyid, passphrase=self.goodpassphrase, publicKeyLocations=arbitraryKeyLoc)
        assert benchmark == signer._get_sig_block(arbitrarySigdata)
     
    def testSign(self):
        origJson = json.loads(self.sampleJSON)
        arbitraryKeyLoc = self.sampleKeyLocations
        
        signer = Sign_0_21(self.goodkeyid, passphrase=self.goodpassphrase, publicKeyLocations=arbitraryKeyLoc)
        signed = signer.sign(origJson)
        
        assert signed.has_key("digital_signature")
        
        sig = signed["digital_signature"]
        assert sig.has_key("signature")
        assert sig["signature"] != None and len(sig["signature"]) > 0
    
    def testSignUnicode(self):
        if self.testDataDir == None:
            log.info("Skipping test, test data directory not set.")
            return
        
        import codecs
        
        fileName = "2011-02-28Metadata1004.json"
        unsigned = json.load(codecs.open(os.path.join(self.testDataDir, fileName), "r", "utf-8-sig"))
        
        arbitraryKeyLoc = self.sampleKeyLocations
        
        signer = Sign_0_21(self.goodkeyid, passphrase=self.goodpassphrase, publicKeyLocations=arbitraryKeyLoc)
        signed = signer.sign(unsigned)
        
        assert signed.has_key("digital_signature")
        
        sig = signed["digital_signature"]
        assert sig.has_key("signature")
        assert sig["signature"] != None and len(sig["signature"]) > 0
        
    def testSignLRTestData(self):
        if self.testDataDir == None:
            log.info("Skipping test, test data directory not set.")
            return
        
        import codecs
        
        allfiles = os.listdir(self.testDataDir)
        for fileName in allfiles:
            log.info("Trying to sign %s" % (fileName, ))
            
            unsigned = json.load(codecs.open(os.path.join(self.testDataDir, fileName), "r", "utf-8-sig"))
        
            arbitraryKeyLoc = self.sampleKeyLocations
            
            signer = Sign_0_21(self.goodkeyid, passphrase=self.goodpassphrase, publicKeyLocations=arbitraryKeyLoc)
            signed = signer.sign(unsigned)
            
            assert signed.has_key("digital_signature")
            
            sig = signed["digital_signature"]
            assert sig.has_key("signature")
            assert sig["signature"] != None and len(sig["signature"]) > 0
        
        
            
        


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testSigning']
    unittest.main()