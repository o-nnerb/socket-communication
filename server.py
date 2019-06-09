from ServerCore import ServerTransaction, ClientThread, ClientConstructor, Comunication, Protocol, ResponseCode

class RequestThread(ClientThread):
    def asUser(self, protocol): pass
    def asGuest(self, protocol):
        if protocol.code == ResponseCode.alive:
            return Comunication.send(Protocol.data("localhost,tcp,9001;localhost,udp,4001".encode()))

    @staticmethod
    def open(ip, port):
        return RequestConstructor(ip, port)

class RequestConstructor(ClientConstructor): 
    def create(self):
        return RequestThread(self)    

class MainTransaction(ServerTransaction):
    def createThread(self, ip, port, conn):
        return RequestThread.open(ip, port).andConnection(conn).shared(self).create()

ServerTransaction.start(MainTransaction.main())