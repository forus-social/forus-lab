import json
import numpy as np
import matplotlib.pyplot as plt

print("hello")

class DataGenerator():
    def __init__(self, length):
        self.length = length

    def get_length(self):
        return self.length
    
test = DataGenerator(100)

print(test.get_length())