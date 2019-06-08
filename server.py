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

TCP_IP = 'localhost'
TCP_PORT = 9001
BUFFER_SIZE = 1024

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

    def auth(self, protocol):
        data = protocol.message.split(":")
        self.isAuthenticated = sign(data[0], data[1])
        if self.isAuthenticated:
            return Comunication.accepted()
        
        return Comunication.notPermitted()

    def asUser(self, protocol):
        if protocol.code == ResponseCode.logout:
            self.isAuthenticated = False
            return Comunication.accepted()
        if protocol.code == ResponseCode.send:
            return self.transaction.send(protocol.message)
        if protocol.code == ResponseCode.receive:
            return self.transaction.receive(protocol.message)
        
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

    @staticmethod
    def tcp():
        t = ServerTransaction(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        t.provider.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        t.provider.bind((TCP_IP, TCP_PORT))
        return t

    def listen(self, integer):
        self.provider.listen(integer)

    def updateThreads(self, thread):
        thread.start()
        self.threads.append(thread)

    def accept(self):
        (conn, (ip,port)) = self.provider.accept()
        print('Got connection from ', (ip,port))
        self.updateThreads(ClientThread.open(ip, port).andConnection(conn).shared(self).create())
   
    def close(self, thread):
        thread.transaction.close()
        self.threads = list(filter(lambda x: x != thread, self.threads))

    @staticmethod
    def start():
        t = ServerTransaction.tcp()
        while True:
            t.listen(5)
            print("Waiting for incoming connections...")
            t.accept()
        

        for t in t.threads:
            t.join()

ServerTransaction.start()