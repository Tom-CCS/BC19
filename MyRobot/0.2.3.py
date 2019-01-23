from battlecode import BCAbstractRobot, SPECS
import battlecode as bc
import random

# Only enable these if you really need them.
#__pragma__('iconv')
#__pragma__('tconv')
#__pragma__('opov')

#Version: 0.2.3 bugfree
#Last Edit: Shengtong Zhang
#Description: This bot will
#1. build pilgrims to mine karbo/fuel and build preacher to attack the opponent's castle
#2. Enable every preacher to carry two positions of enemy's castles; preachers will turn to second location when finished
#3. In case of unexpected path-finding mistakes, preachers will turn back home
#4. Uses a less stable, yet clock-suitable version of DFS proposed by Deng
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

    def receive_initiation(self): #bug free
        for r in self.get_visible_robots():
            if (self.is_radioing(r) and (r.signal_radius <= 2) and (r.signal != 0) and (r.unit == 0)):
                message = r.signal
                mode = message % 4
                message = message // 4
                code = message % 4
                message = message // 4
                y = message % 64
                message = message // 64
                x = message
                self.mode = mode
                self.code = code
                return (x,y)

    def broadcast(self, mode, code, x, y):
        message = (x<<10)+(y<<4)+(code<<2)+mode
        self.signal(message, 2)

    def dist(self,r): #return distance between self and r
        return ((self.me.x - r.x)**2 + (self.me.y - r.y)**2)

    def set_home(self):
        for r in self.get_visible_robots():
            if self.is_visible(r):
                if (r.team == self.me.team) and (r.unit == 0) and (self.dist(r) <= 2):
                    self.home = (r.x,r.y)
                    return True

    def sort_list(self,l):
        for _ in range(len(l)):
            for i in range(len(l)-1):
                if l[i][2] > l[i+1][2]:
                    temp = l[i]
                    l[i] = l[i+1]
                    l[i+1] = temp

    def sign(self,x):
        #sgn
        if (x > 0):
            return 1
        if (x < 0):
            return -1
        return 0

    def set_map_size(self):
        y = len(self.map)
        x = len(self.map[0])
        self.map_size = (x,y)

    def set_symmetry(self):
        if (self.map_size[0] != 0) and (self.map_size[1] != 0):
            self.set_map_size()
            x = self.map_size[0]
            y = self.map_size[1]
            for i in range(x):
                for j in range(y):
                    if self.map[j][i] != self.map[y-j-1][i]:
                        self.map_symmetry = 'V'
                        return True
                    elif self.map[j][i] != self.map[j][x-i-1]:
                        self.map_symmetry = 'H'
                        return True
        self.map_symmetry = 'H'

    def test_Square_In_Bound(self, x, y):
        sq = (x,y)
        if (sq[0] < 0) or (sq[1] < 0):
            return False
        if (sq[0] >= self.map_size[0]) or (sq[1] >= self.map_size[1]):
            return False
        return True

    def rt(self, mapp, start, end, dx):
        # greedy shortest path
        # mapp[i][j] = 0 iff (i, j) is empty
        # dx : the (dx, dy) of movements
        # return : route from start to end (excluding start)
        x = len(mapp)
        y = len(mapp[0])
        z = len(dx)
        fl = [([0 for j in range(y)]) for i in range(x)]
        stack = []
        stack.append(start)
        fl[start[0]][start[1]] = 1
        while(1):
            if(stack[-1][0] == end[0] and stack[-1][1] == end[1]):
                ans = []
                for j in range(len(stack)):
                    ans.append(stack[j])
                return ans
            mns = 10000000
            ns = [0, 0]
            for j in range(z):
                ex = stack[-1][0] + dx[j][0]
                ey = stack[-1][1] + dx[j][1]
                if ex < 0 or ex >= x or ey < 0 or ey >= y:
                    pass
                elif ((mapp[ex][ey] == 0) or (fl[ex][ey] == 1)) :
                    pass
                else:
                    n1 = abs(ex - end[0]) + abs(ey - end[1])
                    if(n1 < mns):
                        mns = n1
                        ns[0] = ex
                        ns[1] = ey
            if(mns != 10000000):
                fl[ns[0]][ns[1]] = 1
                stack.append(ns)
            else:
                stack.pop()
        return []

    def find_route(self, dest, avoid_mine = True, aim = 16): #in combat maneuver, only mark grids inside sight range; bug free
        #The avoid_mine parameter is added to avoid working miners
        """
            Find the shortest (least steps) path to dest.
            Will treat squares as impassable if vulnerable to attack.
            Return value will be:
            (i) A positive integer, indicating the length of such path.
            The path will be automatically stored in self.route
            (ii) False, indicating that there is no such path.
        """
        self.route = []
        x = self.map_size[0]
        y = self.map_size[1]
        new_map = []
        for j in range(y):
            row = []
            for i in range(x):
                passable = self.map[j][i]
                if (avoid_mine):
                    if (self.karbonite_map[j][i] or self.fuel_map[j][i]):
                        passable = False
                row.append(passable)
            new_map.append(row)
            #The first True/False stands for passable/impassable;
            #The second stands for not visited yet. Once visited, it'll be replaced by
            #(parent loc, (dx,dy))
            #Perform BFS
        new_map[dest[1]][dest[0]] = True
        me = self.me
        new_map[me.y][me.x] = True
        #set dest to be passable

        if self.me.unit == 3:
            dirn = [(3,0),(2,2),(0,3),(-2,2),(-3,0),(-2,-2),(0,-3),(2,-2)]
        else:
            dirn = [(2,0),(-2,0),(0,2),(0,-2),(1,1),(1,-1),(-1,1),(-1,-1),(1,0), (0,1),(-1,0), (0, -1)]
        speed = SPECS['UNITS'][me.unit]['SPEED']

        res = self.rt(new_map, (me.y, me.x), (dest[1], dest[0]), dirn)
        j = len(res) - 1
        while j > 0: # the route is reversed as it is in previous code
            self.route.append((res[j][1] - res[j - 1][1], res[j][0] - res[j - 1][0]))
            j -= 1
        #print(len(self.route))
        if len(self.route) == 0:
            return False
        else:
            return len(self.route)

    def identify_attackable_enemies(self):
        #bug free
        enemies = []
        rangee = (1,16) #note
        if (self.me.unit == 4):
            rangee = (16,64)
        for r in self.get_visible_robots():
            if ((self.is_visible(r)) and (r.team != self.me.team)):
                if ((r.x - self.me.x)**2 + (r.y - self.me.y)**2 <= rangee[1]) and ((r.x - self.me.x)**2 + (r.y - self.me.y)**2 >= rangee[0]):
                    enemies.append(r)
            #sorting:
        if (len(enemies) == 0):
            return enemies
        else:
            for _ in range(len(enemies)):
                for i in range(len(enemies)-1):
                    if ((enemies[i].unit < enemies[i + 1].unit) or ((enemies[i].unit == enemies[i + 1].unit) and (enemies[i].id > enemies[i + 1].id))):
                        #enemies[i], enemies[i + 1] = enemies[i+1], enemies[i]
                        tmp = enemies[i + 1]
                        enemies[i + 1] = enemies[i]
                        enemies[i] = tmp
            return enemies

    def set_opponent_castle(self,x,y):
        if (self.map_symmetry == 'V'):
            oppo = (self.map_size[0] - 1 - x, y)
        else:
            oppo = (x, self.map_size[1] - 1 - y)
        return oppo

    def c_talk(self, mes, typee):
        #typee: 1 stands for victory upon target with coords 7x + 3y // 128
        #o stands for sending the coord of itself
        self.castle_talk((typee<<7)+mes)

    def receive_c_talk(self): #return: (mes, typee, id)
        mes = []
        for r in self.get_visible_robots():
            if (r.team == self.me.team) and (r.id != self.me.id):
                talk = r.castle_talk
                if talk != 0:
                    mes.append((r.castle_talk % 128, r.castle_talk // 128, r.id))
        return mes

    def processing_c_talk(self): #bug free
        talk = self.receive_c_talk()
        for (mes, typee, idd) in talk:
            if typee == 0:
                flag = True
                for i in range(len(self.castle_list)):
                    if self.castle_list[i][0] == idd:
                        self.castle_list[i][2] = mes
                        self.dest[1].append(self.set_opponent_castle(self.castle_list[i][1],self.castle_list[i][2]))
                        flag = False
                        break
                if flag:
                    self.castle_list.append([idd, mes, 0])
            elif typee == 1:
                if (7 * self.dest[0][0] + 3 * self.dest[0][1]) // 128 == mes:
                    self.dest[0] = []#False
                    return True
                else:
                    for i in len(self.dest[1]):
                        if (7 * self.dest[1][i][0] + 3 * self.dest[1][i][1]) // 128 == mes:
                            '''del self.dest[1][i]''' #this does not work; change
                            return True

    def test_Valid_Square(self, i): #See if a square is valid for building/moving. i is relative coord.
        visible = self.get_visible_robots()
        x = self.me['x']
        y = self.me['y']
        for r in visible:
            if ('x' not in r):
                pass
            else:
                ux = r.x - x
                uy = r.y - y
                if ((i[0] == ux) and (i[1] == uy)):
                    return False
        if (x + i[0] < 0):
            return False
        elif (y + i[1] < 0):
            return False
        elif (y + i[1] >= self.map_size[1]):
            return False
        elif (x + i[0] >= self.map_size[0]):
            return False
        elif (self.map[y + i[1]][x + i[0]] == True):
            return True
        return False

    def turn(self):
        self.step += 1
        if self.step == 0:
            self.set_map_size()
            self.set_symmetry()
        if self.me.unit == 0:
            if self.step == 0:
                self.castle_num = len(self.get_visible_robots())
                self.castle_talk(self.me.x)
                self.dest = [[],[]]
                self.dest[0] = self.set_opponent_castle(self.me.x,self.me.y)
                for x in range(self.map_size[0]):
                    for y in range(self.map_size[1]):
                        if self.karbonite_map[y][x]:
                            self.karbo_list.append((x,y,(self.me.x - x)**2 +(self.me.y - y)**2))
                self.sort_list(self.karbo_list)
                for d in self.karbo_list:
                    dx = self.sign(d[0] - self.me.x)
                    dy = self.sign(d[1] - self.me.y)
                    if (self.test_Valid_Square((dx, dy))):
                        self.karbonite_pilgrim_direction_list.append((dx, dy))
                    elif (dx != 0) and self.test_Valid_Square((dx, 0)):
                        self.karbonite_pilgrim_direction_list.append((dx, 0))
                    elif (dy != 0) and self.test_Valid_Square((0, dy)):
                        self.karbonite_pilgrim_direction_list.append((0, dy))
                    else:
                        for (dx,dy) in [(1,1),(1,-1),(-1,1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)]:
                            if self.test_Valid_Square((dx,dy)):
                                self.karbonite_pilgrim_direction_list.append((dx, dy))
                for x in range(self.map_size[0]):
                    for y in range(self.map_size[1]):
                        if self.fuel_map[y][x]:
                            self.fuel_list.append((x,y,(self.me.x - x)**2 +(self.me.y - y)**2))
                self.sort_list(self.fuel_list)
                for d in self.fuel_list:
                    dx = self.sign(d[0] - self.me.x)
                    dy = self.sign(d[1] - self.me.y)
                    if (self.test_Valid_Square((dx, dy))):
                        self.fuel_pilgrim_direction_list.append((dx, dy))
                    elif (dx != 0) and self.test_Valid_Square((dx, 0)):
                        self.fuel_pilgrim_direction_list.append((dx, 0))
                    elif (dy != 0) and self.test_Valid_Square((0, dy)):
                        self.fuel_pilgrim_direction_list.append((0, dy))
                    else:
                        for (dx,dy) in [(1,1),(1,-1),(-1,1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)]:
                            if self.test_Valid_Square((dx,dy)):
                                self.fuel_pilgrim_direction_list.append((dx, dy))
            if self.step == 1:
                self.castle_talk(self.me.y)

            self.processing_c_talk()
            if (self.count * self.castle_num <= 2): #very primitive pilgrim building
                self.count += 1
                d = self.karbonite_pilgrim_direction_list[0]
                if self.test_Valid_Square(d):
                    self.karbonite_pilgrim_direction_list = self.karbonite_pilgrim_direction_list[1:]
                    self.broadcast(0,0,self.karbo_list[0][0],self.karbo_list[0][1])
                    self.karbo_list = self.karbo_list[1:]
                    return self.build_unit(2, d[0], d[1])
                else:
                    for d in [(1,1),(1,-1),(-1,1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)]:
                        if self.test_Valid_Square(d):
                            self.karbonite_pilgrim_direction_list = self.karbonite_pilgrim_direction_list[1:]
                            self.broadcast(0,0,self.karbo_list[0][0],self.karbo_list[0][1])
                            self.karbo_list = self.karbo_list[1:]
                            return self.build_unit(2, d[0], d[1])
            elif ((self.fuel >= 60) and (self.karbonite >= 31) and (self.step >= 3)): #Tank attack!
                if len(self.dest[0]) >= 1:
                    if (len(self.dest) >= 2) and (len(self.dest[1]) != 0):
                        self.broadcast(0, 0, self.dest[1][0][0], self.dest[1][0][1]) #TODO: change this
                    else:
                        self.broadcast(0, 0, 0, 0)
                else:
                    self.broadcast(0, 0, self.dest[1][0][0], self.dest[1][0][1])
                for d in [(1,1),(1,-1),(-1,1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)]:
                    if self.test_Valid_Square(d):
                        return self.build_unit(5, d[0], d[1])
            if False:
                self.count += 1
                self.broadcast(3,0,self.fuel_list[0][0],self.fuel_list[0][1])
                self.fuel_list = self.fuel_list[1:]
                for (dx,dy) in [(1,1),(1,-1),(-1,1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)]:
                    if self.test_Valid_Square((dx,dy)):
                        return self.build_unit(2, dx, dy)
                for (dx,dy) in [(1,1),(1,-1),(-1,1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)]:
                    if self.test_Valid_Square((dx,dy)):
                        return self.build_unit(2, dx, dy)

        if self.me.unit == 2: #bug free
            if self.step == 0:
                self.set_home()
                mes = self.receive_initiation()
                self.dest.append((mes[0],mes[1]))
                self.find_route(self.dest[0], aim = 0)
                self.forward_route = self.route[0:]
                for i in range(len(self.route)):
                    self.back_route.append((-self.route[len(self.route) - 1 - i][0],-self.route[len(self.route) - 1 - i][1]))
            if len(self.route) > 0:
                move = self.route[-1]
                if self.test_Valid_Square(move):
                    self.route = self.route[:-1]
                    return self.move(move[0],move[1])
            elif (self.me.x == self.dest[0][0]) and (self.me.y == self.dest[0][1]) and (self.me.fuel < 100) and (self.me.karbonite < 20): ###
                return self.mine()
            elif (self.me.x == self.dest[0][0]) and (self.me.y == self.dest[0][1]) and (len(self.back_route) > 0):
                self.route = self.back_route[0:]
                move = self.route[-1]
                if self.test_Valid_Square(move):
                    self.route = self.route[:-1]
                    return self.move(move[0],move[1])
            else:
                if (len(self.forward_route) > 0):
                    self.route = self.forward_route[0:] #this might result in error, yet works
                return self.give(self.home[0] - self.me.x, self.home[1] - self.me.y, self.me.karbonite, self.me.fuel)

        if self.me.unit == 5:
            self.log(self.dest)
            if self.step == 0:
                self.set_home()
                mes = self.receive_initiation()
                if self.code == 0:
                    self.dest.append(self.set_opponent_castle(self.home[0],self.home[1]))
                self.dest.append((mes[0],mes[1]))
                return None
            targets = self.identify_attackable_enemies()
            if len(targets) != 0:
                return self.attack(targets[0].x - self.me.x, targets[0].y - self.me.y)
            elif len(self.route) > 0:
                move = self.route[-1]
                if self.test_Valid_Square(move):
                    self.still = 0
                    self.route = self.route[:-1]
                    return self.move(move[0],move[1])
                else:
                    self.still += 1
                if (self.still >= 5):
                    self.route = []
                    if (len(self.dest) > 0): #Note: the judgement for reason of "traffic jam" need improvements
                        self.dest = self.dest[1:]
                    else:
                        self.dest = [self.home]
            else:
                if (len(self.dest) == 0):
                    self.dest = [self.home] #move randomly for now
                if (self.dest[0][0] - self.me.x)**2 + (self.dest[0][1] - self.me.y)**2 <= 16:
                    self.c_talk((7*self.dest[0][0] + 3*self.dest[0][1])//128, 1)
                    self.dest = self.dest[1:]
                if (len(self.dest) > 0):
                    self.find_route(self.dest[0], aim = 16)
                    move = self.route[-1]
                    if self.test_Valid_Square(move):
                        self.route = self.route[:-1]
                        return self.move(move[0],move[1])
robot = MyRobot()
