import base64
import os
import os.path
import hashlib
from enum import Enum


class ResponseCode(Enum):
    error = 0       # Generic situations
    buffer = 100

    # actions
    send = 101
    receive = 102
    fragment = 103
    checkSum = 104
    fileSizeExceeded = 105
    bytesError = 106

    auth = 110
    logout = 111

    # success
    accepted = 200
    refused = 400
    notPermitted = 401

class Protocol:
    code = ResponseCode.accepted
    message = ""

    def __init__(self, code, message):
        self.code = code
        self.message = message

    @staticmethod
    def error(message):
        return Protocol(ResponseCode.error, message)
    
    @staticmethod
    def buffer(BUFFER_SIZE):
        return Protocol(ResponseCode.buffer, str(BUFFER_SIZE))

    @staticmethod
    def send(filename):
        return Protocol(ResponseCode.send, filename)

    @staticmethod
    def receive(filename):
        return Protocol(ResponseCode.receive, filename)

    @staticmethod
    def checkSum(checkSum):
        return Protocol(ResponseCode.checkSum, checkSum)

    @staticmethod
    def fragment(bufferSize=0, file=None):
        if not file:
            return Protocol(ResponseCode.fragment, "")
        
        return Protocol(ResponseCode.fragment, file.next(1, bufferSize - Protocol.byteSize(Protocol.fragment().asData())))

    @staticmethod
    def bytesError():
        return Protocol(ResponseCode.bytesError, "Bytes Errors")

    @staticmethod
    def fileSizeExceeded():
        return Protocol(ResponseCode.fileSizeExceeded, "File Size Exceeded")

    @staticmethod
    def auth(username, password):
        return Protocol(ResponseCode.auth, str(username)+":"+str(password))
    
    @staticmethod
    def logout():
        return Protocol(ResponseCode.logout, "Logout")

    @staticmethod
    def accepted():
        return Protocol(ResponseCode.accepted, "Accepted")
    
    @staticmethod
    def refused():
        return Protocol(ResponseCode.refused, "Refused")

    @staticmethod
    def notPermitted():
        return Protocol(ResponseCode.notPermitted, "Not Permitted")

    def asRaw(self):
        middle = ""
        if type(self.message) != bytes:
            middle = str(self.message)
        
        return "<Protocol-"+str(self.code.value)+"-"+middle+"->"

    @staticmethod
    def byteSize(data):
        size = 0
        for byte in data:
            size += 1
        return size

    @staticmethod
    def toBinary(data):
        array = [int(format(byte, "08b"), 2) for byte in data]
        return bytes(array)

    def asData(self):
        if type(self.message) == bytes:
            raw = self.asRaw()
            raw = Protocol.toBinary(raw[0:len(raw)-len("->")].encode()) + Protocol.toBinary(self.message) + Protocol.toBinary("->".encode())

            return raw

        return Protocol.toBinary(self.asRaw().encode())
    
    @staticmethod
    def fromData(data):        
        header = data[0:len("<Protocol-")].decode()
        if header != "<Protocol-":
            return None
    
        footer = data[len(data)-len("->"):len(data)].decode()
        if footer != "->":
            return None
        
        def nextParam(data):
            array = []
            for c in data:
                c = chr(c)
                if c == "-":
                    break
                array.append(c)
            return "".join(array)

        middle = data[len("<Protocol-"):len(data)-len("->")]
        code = nextParam(middle)
        middle = middle[len(code)+1:]
        message = middle
        
        code = ResponseCode(int(code))
        if code != ResponseCode.fragment:
            return Protocol(code, message.decode())
        
        return Protocol(code, message) 
    
    def asString(self):
        return "Protocol "+ str(self.code.value) +"\nMessage: "+ str(self.message) +"\n"

class FileByte:
    file = None
    fragments = []
    bufferSize = 0
    # mode {0 == normal}; {1 == buffer}
    mode = 0
    isWritabble = False
    name = ""

    def __init__(self, filename, file, bufferSize = 0):
        self.file = file
        self.mode = int(bufferSize == 0)
        self.fragments = []
        self.bufferSize = bufferSize
        self.eof = False
        self.isWritabble = False
        self.name = filename

    def endOfFile(self):
        return self.eof

    def chunck(self, bufferSize=0):
        if bufferSize >= 1:
            return self.file.read(bufferSize)
        return self.file.read(self.bufferSize)

    def next(self, fragmentSize=1, bufferSize=0):
        if self.eof:
            return
        if len(self.fragments) == 0:            
            for i in range(0, fragmentSize):
                data = self.chunck(bufferSize)
                if not data:
                    self.eof = True
                    return "".encode()
                
                self.fragments.append(data)
            
        return self.fragments.pop(0)

    def append(self, data, fragmentSize=1):
        if len(self.fragments) >= fragmentSize:
            for fragment in self.fragments:
                self.file.write(fragment)
            self.fragments = []
        
        self.fragments.append(data)

    def saveAndClose(self):
        if not self.isWritabble:
            self.close()
            return
        
        for fragment in self.fragments:
            self.file.write(fragment)
        
        self.close()

    @staticmethod
    def open(filename, bufferSize=0, toWrite=True):
        if not toWrite and not os.path.isfile(filename):
            return None

        status = "b"
        if toWrite:
            status = "w"+status
        else:
            status = "r"+status
        fileb = FileByte(filename, open(filename, status), bufferSize)        
        fileb.isWritabble = toWrite
        return fileb

    def close(self):
        self.file.close()
        self.fragments = []

    def md5(self):
        hash_md5 = hashlib.md5()
        with open(self.name, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

class Comunication:
    __send = None

    __bufferSize = 0
    __onResponse = None

    def __init__(self):
        self.__send = None
        self.__onResponse = None
        self.__bufferSize = 0
    
    @staticmethod
    def send(protocol):
        self = Comunication()
        self.__send = protocol
        return self

    def onResponse(self, function):
        self.__onResponse = function
        return self
    
    def bufferSize(self, bufferSize):
        self.__bufferSize = bufferSize
        return self

    @staticmethod
    def empty():
        return Comunication()
    
    def execute(self, socket, isRecursive=False):
        if self.__send:
            socket.send(self.__send.asData())

        if not self.__onResponse:
            return self.__send
        
        result = self.__onResponse(socket.recv(self.__bufferSize))
        
        if type(result) == Comunication and not isRecursive:
            return result.execute(socket)
        
        return result # must be a bool value or Protocol

    def recursive(self, socket):
        communication = self
        while type(communication) == Comunication:
            communication = communication.execute(socket, True)
        
        return communication

    def transform(self, any):
        self.__placeholder = any
        return self

    @staticmethod
    def accepted():
        return Comunication.send(Protocol.accepted())
    
    @staticmethod
    def refused():
        return Comunication.send(Protocol.refused())

    @staticmethod
    def notPermitted():
        return Comunication.send(Protocol.notPermitted())
        
class Transaction:
    provider = None
    bufferSize = 1024

    def __init__(self, provider, bufferSize=1024, ip=None, port=None):
        self.provider = provider
        self.bufferSize = bufferSize
        self.ip = ip
        self.port = port

    def connect(self, ip, port):
        self.provider.connect((ip, port))
    
    def close(self):
        self.provider.close()
        print('Connection Closed')

    # main communication function
    # should be used in every simple protocol transaction
    def commit(self, comunication):
        return comunication.bufferSize(self.bufferSize).execute(self.provider)

    # helper functions
    def accepted(self):
        return Comunication.accepted().execute(self.provider)

    def refused(self):
        return Comunication.refused().execute(self.provider)

    def send(self, filename):
        global file
        file = FileByte.open(filename, self.bufferSize, False)

        if not file:
            return self.refused()

        if os.stat(file.name).st_size > 5242880:
            return Comunication.send(Protocol.fileSizeExceeded()).execute(self.provider)

        def willEnd(response):
            protocol = Protocol.fromData(response)
            if not protocol:
                return Comunication.refused()

            return protocol

        def onResponse(response):
            protocol = Protocol.fromData(response)
            if not protocol:
                return Comunication.refused()
            
            if protocol.code != ResponseCode.accepted:
                return protocol
            
            if file.endOfFile():
                file.close()
                return Comunication.send(Protocol.checkSum(file.md5())).onResponse(willEnd).bufferSize(self.bufferSize)

            return Comunication.send(Protocol.fragment(self.bufferSize, file)).onResponse(onResponse).bufferSize(self.bufferSize)

        def onBufferSync(response):
            protocol = Protocol.fromData(response)
            if not protocol:
                return Comunication.refused()
            
            print(protocol.asString())
            if protocol.code != ResponseCode.accepted:
                return protocol
            
            return Comunication.send(Protocol.buffer(self.bufferSize)).bufferSize(self.bufferSize).onResponse(onResponse).recursive(self.provider)
        
        return Comunication.send(Protocol.receive(filename)).bufferSize(self.bufferSize).onResponse(onBufferSync).execute(self.provider)

    def receive(self, filename):
        global file
        global bufferSize
        file = None
        bufferSize = self.bufferSize

        def onResponse(response):
            protocol = Protocol.fromData(response)
            if not protocol:
                return Comunication.refused()
            
            if protocol.code == ResponseCode.fragment:
                file.append(protocol.message)
                return Comunication.accepted().bufferSize(self.bufferSize).onResponse(onResponse)
            
            file.saveAndClose()
            if protocol.code != ResponseCode.checkSum:
                return protocol
                
            if protocol.message != file.md5():
                return Comunication.send(Protocol.bytesError()).bufferSize(self.bufferSize)
            return Comunication.accepted().bufferSize(self.bufferSize)

        def onBufferSync(response):
            protocol = Protocol.fromData(response)
            if not protocol:
                return Comunication.refused()
            
            if protocol.code != ResponseCode.buffer:
                return protocol

            bufferSize = int(protocol.message)
            return Comunication.accepted().onResponse(onResponse).bufferSize(bufferSize).recursive(self.provider)

        def onReceiveProtocol(response):
            global file

            protocol = Protocol.fromData(response)
            if not protocol:
                return Comunication.refused()
            
            print("Client 2", protocol.asRaw())
            if protocol.code != ResponseCode.receive:
                # protocol.code == .fileSizeExceeded or protocol.code == .refused
                return protocol

            file = FileByte.open(filename, self.bufferSize, True)
            return Comunication.accepted().onResponse(onBufferSync).bufferSize(self.bufferSize).execute(self.provider)
        
        return Comunication.send(Protocol.send(filename)).onResponse(onReceiveProtocol).bufferSize(self.bufferSize).recursive(self.provider)

    def clientSend(self, filename):
        def onResponse(response):
            protocol = Protocol.fromData(response)
            if not protocol:
                return Comunication.refused()
            
            if protocol.code != ResponseCode.send:
                return protocol
            
            return self.send(filename)
        
        return Comunication.send(Protocol.receive(filename)).onResponse(onResponse).bufferSize(self.bufferSize).execute(self.provider)

    def waitForResponse(self):
        def onResponse(response):
            print(response)
            return Protocol.fromData(response)

        return Comunication.empty().onResponse(onResponse).bufferSize(self.bufferSize).execute(self.provider)
#byteslen = 1024
#file = FileByte.open("abc.txt", byteslen, False)
#print(Protocol.fromData(Protocol.fragment(byteslen, file).asData()).message.decode())