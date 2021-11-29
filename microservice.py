import requests

class Microservice:
  ip = ''
  dependencies = []
  max_age = 0

  def __init__(self, host, d):
    self.ip = host
    self.dependencies = d
    self.max_age = 0

  def __hash__(self) -> int:
    return hash(self.ip)
    
  
