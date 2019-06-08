# client2.py
#!/usr/bin/env python

import socket
from NetworkCore import Protocol, Transaction, ResponseCode, Comunication

class Any: pass

def prefix(pre, string):
    if len(string) < len(pre):
        return False
    
    return pre == string[0:len(pre)]

# Is methods
def isAuth(message):
    if not prefix("auth", message):
        return (False, (None, None))
    
    auth = "".join(message.split("auth ")).split(":")
    if len(auth) != 2:
        return (False, (None, None))

    return (True, (auth[0], auth[1]))

def isLogout(message):
    return prefix("logout", message)

def isSend(message):
    if not prefix("send", message):
        return (False, None)
    
    filename = "".join(message.split("send ")).split(" ")
    if len(filename) != 1:
        return (False, None)

    return (True, filename[0])

def isReceive(message):
    if not prefix("receive", message):
        return (False, None)
    
    filename = "".join(message.split("receive ")).split(" ")
    if len(filename) != 1:
        return (False, None)

    return (True, filename[0])

def commit(protocol):
    def onResponse(data):
        return Protocol.fromData(data)
        
    return transaction.commit(Comunication.send(protocol).onResponse(onResponse))

def printProtocol(protocol, responsesCodes=[]):
    if len(responsesCodes) == 0:
        return None

    if not protocol:
        print("Error in protocol communication")
        return None

    for (code, message) in responsesCodes:
        if not code or type(protocol) != Protocol:
            print(message)
            return protocol

        if protocol.code == ResponseCode.error:
            print(protocol.asString())
            return protocol

        if id(code) == id(Any) or protocol.code == code:
            print("\n"+protocol.asString())
            print(message)
            return protocol
    
    return protocol

def mayBeAuth(message):
    result = isAuth(message)
    if not result[0]:
        return False

    (username, password) = result[1]
    
    printProtocol(commit(Protocol.auth(username, password)), [
        (ResponseCode.accepted, "Authorized Connection"),
        (ResponseCode.notPermitted, "Wrong username or password"),
        (Any, "Command helper: \"auth user:password\"")
    ])

    return True

def mayBeLogout(message):
    if not isLogout(message):
        return False
    
    printProtocol(commit(Protocol.logout()), [
        (ResponseCode.accepted, "Logout Successfully"),
        (Any, "Command helper: \"logout\"")
    ])

def mayBeSend(message):
    result = isSend(message)
    if not result[0]:
        return False
    
    printProtocol(transaction.receive(result[1]), [
        (ResponseCode.checkSum, "Successfuly received"),
        (ResponseCode.accepted, "Successfuly received file"),
        (Any, "Server can't send file")
    ])

def mayBeReceive(message):
    result = isReceive(message)
    if not result[0]:
        return False
    
    printProtocol(transaction.clientSend(result[1]), [
        (ResponseCode.accepted, "Successfuly sended File"),
        (ResponseCode.checkSum, "Error during Transmission"),
        (Any, "Can't send file")
    ])

def atLeastOne(message, functions):
    for handler in functions:
        if handler(message):
            return True
    
    return False

#print(id(Any) == id(Any))
#exit()

transaction = Transaction(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
transaction.connect('localhost', 9001)

while True:
    message = input(":: ")
    if message == 'q':
        break
    
    atLeastOne(message, [
        mayBeAuth,
        mayBeLogout,
        mayBeSend,
        mayBeReceive
    ])

#with open('received_file', 'wb') as f:
#    print('file opened')
#    while True:
#        #print('receiving data...')
#        data = s.recv(BUFFER_SIZE)
#        print('data=%s', (data))
#        if not data:
#            f.close()
#            print('file close()')
#            break
        # write data to a file
#        f.write(data)

# print('S')
transaction.close()