# client2.py
#!/usr/bin/env python
import sys, random, time
import threading

import socket
from NetworkCore import Protocol, Transaction, ResponseCode, Comunication

transaction = Transaction(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
transaction.connect('localhost', 9889)

def onResponse(response):
      print(response)
      protocol = Protocol.fromData(response)
      if (not protocol):
            return

      if protocol.code == ResponseCode.accepted:
            print("Worker: did produce one item")
            return

      if protocol.code == ResponseCode.refused:
            print("Worker: sleeping")
            return
      
      print("Worker: error")

while (True):
      transaction = Transaction(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
      transaction.connect('localhost', 9889)
      transaction.commit(Comunication.send(Protocol.data("1".encode())).onResponse(onResponse))
      transaction.close()
      time.sleep(random.randint(0, 5))