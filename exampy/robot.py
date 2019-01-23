from battlecode import BCAbstractRobot, SPECS
import battlecode as bc
import random

# Only enable these if you really need them.
#__pragma__('iconv')
#__pragma__('tconv')
#__pragma__('opov')

#Version: 0.0
#Last Edit: Shengtong Zhang
#Description: This bot does nothing. Used for debugging
class MyRobot(BCAbstractRobot):
    def __init__(self):
        BCAbstractRobot.__init__(self)
        self.castle_num = 0
        self.step = -1 # turn count
        self.dest = [] #default as invalid
        self.home = (0,0) #for handing in resources
        self.map_size = (0,0)
        self.map_symmetry = False #V means a[i][j] = a[t - i][j], H means otherwise
        self.mode = 0 #0 for karbo, 1 for rushing, 3 for fuel
        self.code = 0 #0: home oppo first, then dest in the message; 1: direct to the mes.
        self.castle_list = [] #format: [id, x, y]
        self.fuel_list = [] #list of locs of fuel, sorted by dist
        self.karbo_list = [] #list of locs of karbo, sorted by dist
        self.count = 0 #Set up a count for building units
        self.route = []
        self.forward_route = [] #For pilgram only
        self.back_route = []
        self.karbonite_pilgrim_direction_list = [] #optimization for neighboring mines
        self.fuel_pilgrim_direction_list = []
        self.still = 0 #In case of unexpected bugs
        self.level_map = [] #"output" of new BFS. Will record the level of each node to the dest.
    
    def turn(self):
        a = 1
            
robot = MyRobot()
