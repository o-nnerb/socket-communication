# server2.py
import os
import os.path
import socket
from threading import Thread
from socketserver import ThreadingMixIn
import pymysql
import pymysql.cursors
from NetworkCore import Protocol, Transaction, ResponseCode, Comunication

def startConnection():
    return pymysql.connect(host='localhost',
                             user='dev',
                             password='123456',
                             db='python_socket',
                             charset='utf8mb4',
                             cursorclass=pymysql.cursors.DictCursor)

def sign(username, password):
    conn = startConnection()
    with conn.cursor() as cursor:
        sql = "SELECT `username` from `user` where `username`=%s and `password`=%s"
        cursor.execute(sql, (username, password))
        result = cursor.fetchone()
        conn.close()
        return type(result) == dict and len(result) >= 1
    
    conn.close()
    return False

class ClientThread(Thread):
    ip = 0
    port = 0
    transaction = None
    server = None

    def __init__(self, constructor):
        Thread.__init__(self)
        self.ip = constructor.ip
        self.port = constructor.port
        self.transaction = constructor.transaction
        self.server = constructor.server
        self.isAuthenticated = False
        self.username = ""

    def auth(self, protocol):
        data = protocol.message.split(":")
        self.isAuthenticated = sign(data[0], data[1])
        if self.isAuthenticated:
            self.username = data[0]
            return Comunication.accepted()
        
        return Comunication.notPermitted()
    
    def path(self):
        if self.isAuthenticated:
            return "public/"+str(self.username)+"/"
        return "public/"

    def listFiles(self):
        path = self.path()
        onlyfiles = ";".join([f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))])
        return Comunication.send(Protocol.data(onlyfiles.encode()))

    def asUser(self, protocol):
        if protocol.code == ResponseCode.logout:
            self.isAuthenticated = False
            self.username = ""
            return Comunication.accepted()
        if protocol.code == ResponseCode.send:
            if len(protocol.message.split("/")) >= 2:
                return self.transaction.refused()

            return self.transaction.send(self.path()+protocol.message)

        if protocol.code == ResponseCode.receive:
            if len(protocol.message.split("/")) >= 2:
                return self.transaction.refused()

            return self.transaction.receive(self.path()+protocol.message)

        if protocol.code == ResponseCode.listFiles:
            return self.listFiles()
        
    def asGuest(self, protocol):
        if protocol.code == ResponseCode.auth:
            return self.auth(protocol)

        return Comunication.send(Protocol.notPermitted())

    def didReceived(self, protocol):
        if self.isAuthenticated:
            toCommit = self.asUser(protocol)
        else:
            toCommit = self.asGuest(protocol)

        if not toCommit:
            self.transaction.commit(Comunication.refused())
            return
        
        if type(toCommit) == Comunication:
            self.transaction.commit(toCommit)
        
    def observe(self):
        protocol = self.transaction.waitForResponse()
        if not protocol:
            self.transaction.commit(Comunication.send(Protocol.cutConnection()))
            return False

        print(protocol.asRaw())
        self.didReceived(protocol)
        return True

    def run(self):
        while True:
            if not self.observe():
                break
        self.server.close(self)
    
    @staticmethod
    def open(ip, port):
        return ClientConstructor(ip, port)

class ClientConstructor:
    ip = 0
    port = 0
    transaction = None
    server = None

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.transaction = None
        self.server = None
    
    def andConnection(self, conn):
        self.transaction = Transaction(conn)
        return self
    
    def shared(self, server):
        self.server = server
        return self
    
    def create(self):
        return ClientThread(self)

class ServerTransaction(Transaction):
    threads = []
    name = ""
    port = 0

    @classmethod
    def main(self):
        return self.tcp("localhost", 9000)

    @classmethod
    def udp(self, ip, port):
        t = self(socket.socket(socket.AF_INET, socket.SOCK_DGRAM))
        t.provider.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        t.provider.bind((ip, port))
        return t

    @classmethod
    def tcp(self, ip, port):
        t = self(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        t.provider.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        t.provider.bind((ip, port))
        return t

    def listen(self, integer):
        self.provider.listen(integer)

    def updateThreads(self, thread):
        thread.start()
        self.threads.append(thread)

    def createThread(self, ip, port, conn):
        return ClientThread.open(ip, port).andConnection(conn).shared(self).create()

    def accept(self):
        (conn, (ip,port)) = self.provider.accept()
        print('Got connection from ', (ip,port))
        self.updateThreads(self.createThread(ip, port, conn))
   
    def close(self, thread):
        thread.transaction.close()
        self.threads = list(filter(lambda x: x != thread, self.threads))

    @staticmethod
    def start(server):
        print(server)
        while True:
            try:
                server.listen(5)
            except: pass
            print("Waiting for incoming connections...")
            server.accept()
        
        for t in server.threads:
            t.join()
