from battlecode import BCAbstractRobot, SPECS
import battlecode as bc
import random

# Only enable these if you really need them.
#__pragma__('iconv')
#__pragma__('tconv')
#__pragma__('opov')

#Version: 1.0.1
#Last Edit: Stephan Xie
#Description:
#This bot merges version 0.2.3/4/5
#And can:
#Build pilgram to mine resources
#Build church
#Use preacher rush
#Build prophet lattice
#Attack enemy's mines

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
        self.still = 0 #In case of unexpected bugs
        self.level_map = [] #"output" of new BFS. Will record the level of each node to the dest.
        self.temp_map = [] #for crusader to mark the dangerous regions
        self.flag = False
        self.far_mine_list = []
        self.lonely_mine_list = []
        self.castle = None
        self.nearby_karbonite_mine = []
        self.nearby_fuel_mine = []
        self.waiting_for_church = False
        self.built_church = False
        self.stop_building = False
        self.artillary_lattice = [] #spamming artillary
        self.karbonite_pilgrim_direction_list = [] #optimization for neighboring mines
        self.fuel_pilgrim_direction_list = []
        self.crusader_count = 0
        self.global_turn = 0
        self.nearby_pilgrim_replenish_list = {}
    
    def artillary_lattice_initialize(self):
        dirn = self.dirns(100)
        for (i,j) in dirn:
            if (self.test_Valid_Square((i,j))) and (i % 2 == j % 2) and(i ** 2 + j ** 2 >= 8):
                self.artillary_lattice.append((self.me.x + i, self.me.y + j, i ** 2 + j ** 2))
        self.sort_list(self.artillary_lattice)

    def find_nearby_karbonite_mine(self): #mines centered around self
        x = self.me.x
        y = self.me.y
        for (i,j) in self.dirns(16):
            if self.test_Square_In_Bound(x + i, y + j) and self.karbonite_map[y + j][x + i]:
                self.nearby_karbonite_mine.append((x + i, y + j))
                self.nearby_pilgrim_replenish_list[(x + i) * 100 +  y + j] = 0
            if self.test_Square_In_Bound(x + i, y + j) and self.fuel_map[y + j][x + i]:
                self.nearby_fuel_mine.append((x + i, y + j))


    def replenish_nearby_pilgrim(self):
        #self.log(self.nearby_pilgrim_replenish_list)
        for r in self.get_visible_robots():
            for t in self.nearby_pilgrim_replenish_list.keys():
                t0 = t // 100
                t1 = t % 100
                if (r.team == self.me.team) and (r.unit == 2) and (r.x == t0) and (r.y == t1):
                    self.nearby_pilgrim_replenish_list[t] = 0
        for t in self.nearby_pilgrim_replenish_list.keys():
            self.nearby_pilgrim_replenish_list[t] += 1
            if (self.nearby_pilgrim_replenish_list[t] > 10):
                placed = False
                t0 = t // 100
                t1 = t % 100
                for l in self.nearby_karbonite_mine:
                    if (l[0] == t0) and (l[1] == t1):
                        placed = True
                if not placed:
                    self.nearby_karbonite_mine.append((t0, t1))
                    self.nearby_pilgrim_replenish_list[t] = -100


    def dirns(self,radi):
        res = []
        dx = 0
        dy = 0
        while dx**2 <= radi:
            while dy**2 + dx**2 <= radi:
                res.append((dx,dy))
                if dx != 0:
                    res.append((-dx,dy))
                if dy != 0:
                    res.append((dx,-dy))
                if dx != 0 and dy != 0:
                    res.append((-dx,-dy))
                dy+=1
            dy = 0
            dx += 1
        return res[1:]
    
    def find_dest(self): #determine the destination of far-going pilgrims
        hom_x = self.home[0]
        hom_y = self.home[1]
        mines = []
        for (i,j) in self.dirns(16):
            if self.fuel_map[hom_y + j][hom_x + i] or self.karbonite_map[hom_y + j][hom_x + i]:
                valid = True
                for r in self.get_visible_robots():
                    if (r.x == hom_x + i) and (r.y == hom_y + j) and (r.id != self.id):
                        valid = False
                if (valid):
                    mines.append((hom_x + i, hom_y + j, i ** 2 + j ** 2))
        self.sort_list(mines)
        self.dest = (mines[0][0], mines[0][1])
    
    def find_mine_cluster(self):
        #define a mine-cluster as a dirn(16) area around a certain point.
        #run at turn 0
        mine_array = []
        for i in range(self.map_size[0]):
            for j in range(self.map_size[1]):
                if (self.karbonite_map[j][i] or self.fuel_map[j][i]):
                    near_castle = False
                    for r in self.castle_list:
                        if (r[1] - i) ** 2 + (r[2] - j) ** 2 <= 16:
                            near_castle = True
                    if not near_castle:
                        mine_array.append((i,j))
        turn = 0
        while (len(mine_array) > turn):
           count = 0
           new_mine_array = []
           x = mine_array[0]
           for s in mine_array:
               if ((s[0] - x[0]) ** 2 + (s[1] - x[1]) ** 2<= 16):
                   count += 1
               else:
                   new_mine_array.append(s)
           if (count >= 4):
               mine_array = new_mine_array
               self.far_mine_list.append((x[0],x[1], (self.me.x - x[0]) ** 2 + (self.me.y - x[1]) ** 2))
               turn = 0
           else:
               mine_array = mine_array[1:] + [mine_array[0]]
               turn += 1
        for (i,j) in mine_array:
            self.lonely_mine_list.append((i,j, (self.me.x - i) ** 2 + (self.me.y - j) ** 2))
        self.sort_list(self.far_mine_list)
        self.sort_list(self.lonely_mine_list)
    
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
    
    def identify_pilgram(self):
        robots = self.get_visible_robots()
        for r in robots:
            if ((self.is_visible(r)) and (r.team != self.me.team)):
                if r.unit == 2:
                    pos = (r.x,r.y)
                    return pos
        return False
    
    def check_halfcourt(self):#returns a function that taks in a position and returns True iff it's in enemy's halfcourt
        if (self.map_symmetry == "H"):
            y = self.map_size[1]
            if (self.home[1] >= y/2):
                return lambda x1,y1: y1 < (y/2)
            else:
                return lambda x1,y1: y1 >= (y/2)
        else:
            x = self.map_size[0]
            if (self.home[0] >= x/2):
                return lambda x1,y1: x1 < (x/2)
            else:
                return lambda x1,y1: x1 >= (x/2)
    
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
                return (x,y,mode,code)
        return False
    
    def sign(self,x):
        #sgn
        if (x > 0):
            return 1
        if (x < 0):
            return -1
        return 0
    
    def generate_destinations(self): #generate a list of mines in the enemy's halfcourt
        #Will filter out (nearly) all mines that's within the castle's protection
        res = []
        x = self.map_size[0]
        y = self.map_size[1]
        fuel = self.fuel_map
        karbo = self.karbonite_map
        f = self.check_halfcourt()
        for dx in range(x):
            for dy in range(y):
                if fuel[dy][dx] or karbo[dy][dx]:
                    if f(dx,dy):
                        flag = True
                        for (cx,cy) in self.dest:
                            if (cx - dx)**2 + (cy - dy)**2 < 16:
                                flag = False
                                break
                        if flag:
                            res.append((dx,dy))
        self.dest = res[:]
    
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
                    self.global_turn = r.turn
                    return True
    def set_opponent_castle(self,x,y):
        if (self.map_symmetry == 'V'):
            oppo = (self.map_size[0] - 1 - x, y)
        else:
            oppo = (x, self.map_size[1] - 1 - y)
        return oppo
    
    def sort_list(self,l):
        for _ in range(len(l)):
            for i in range(len(l)-1):
                if l[i][2] > l[i+1][2]:
                    temp = l[i]
                    l[i] = l[i+1]
                    l[i+1] = temp
                    
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
    
    def mark_dangerous_regions(self, enemies):#enemies: a list. Format: [(pos1),(pos2)]. Default atk_range: 8
        def dirns(radi):
            res = []
            dx = 0
            dy = 0
            while dx**2 <= radi:
                while dy**2 + dx**2 <= radi:
                    res.append((dx,dy))
                    if dx != 0:
                        res.append((-dx,dy))
                    if dy != 0:
                        res.append((dx,-dy))
                    if dx != 0 and dy != 0:
                        res.append((-dx,-dy))
                    dy+=1
                dy = 0
                dx += 1
            return res
        scale = dirns(64)
        x = self.map_size[0]
        y = self.map_size[1]
        
        self.temp_map = []
        for i in range(y):
            self.temp_map.append(self.map[i][0:])
        
        for (cx,cy) in enemies:
            for (dx,dy) in scale:
                tx = cx+dx
                ty = cy+dy
                if tx >= 0 and tx < x:
                    if ty >= 0 and ty < y:
                        self.temp_map[ty][tx] = False
    
    def BFS(self, dest, aim, speed = False):
        #aim: the scale of the dest.
        #e.g. if the goal is to attack the object at dest, then set aim = attack_range
        #if the goal is to hand in resources, then set aim = 2
        #check if self is within aim of dest!!!
        mp = []
        sf_map = self.temp_map
        x,y = self.map_size
        d_x, d_y = dest
        me_x = self.me.x
        me_y = self.me.y
        
        for i in range(y):
            mp.append(sf_map[i][0:]+3*[False])
        mp.append((3+x)*[False])
        mp.append((3+x)*[False])
        mp.append((3+x)*[False])
        
        def dirns(radi):
            res = []
            dx = 0
            dy = 0
            while dx**2 <= radi:
                while dy**2 + dx**2 <= radi:
                    res.append((dx,dy))
                    if dx != 0:
                        res.append((-dx,dy))
                    if dy != 0:
                        res.append((dx,-dy))
                    if dx != 0 and dy != 0:
                        res.append((-dx,-dy))
                    dy+=1
                dy = 0
                dx += 1
            return res
        
        scale = dirns(aim)
        stack = []
        
        for (dx,dy) in scale:
            tx = d_x+dx
            ty = d_y+dy
            if tx >=0 and tx < x:
                if ty >= 0 and ty < y:
                    if mp[ty][tx] == True:
                        mp[ty][tx] = 2
                        stack.append((tx, ty))
        if speed == False:    
            speed = SPECS['UNITS'][self.me.unit]['SPEED']
        dirn = dirns(speed)
        if speed == 9:
            dirn = {(3,0),(-3,0),(0,3),(0,-3),(2,2),(2,-2),(-2,2),(-2,-2)}
        count = 0
        mp[me_y][me_x] = "S"
        
        maxlevel = 100
        
        while len(stack) > count:
            (c_x,c_y) = stack[count]
            level = mp[c_y][c_x] + 1
            if (level > maxlevel + 1):
                self.level_map = mp
                return True
            for (dx,dy) in dirn:
                t_x = c_x+dx
                t_y = c_y+dy
                if mp[t_y][t_x] == True:
                    mp[t_y][t_x] = level
                    stack.append((t_x,t_y))
                elif mp[t_y][t_x] == "S":
                    mp[t_y][t_x] = level
                    maxlevel = level
            count += 1
        return False
    
    def test_Square_In_Bound(self, x, y):
        sq = (x,y)
        if (sq[0] < 0) or (sq[1] < 0):
            return False
        if (sq[0] >= self.map_size[0]) or (sq[1] >= self.map_size[1]):
            return False
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
    
    def receive_c_talk(self): #return: (mes, typee, id)
        mes = []
        for r in self.get_visible_robots():
            if (r.team == self.me.team) and (r.id != self.me.id):
                talk = r.castle_talk
                if talk != 0:
                    mes.append((r.castle_talk % 128, r.castle_talk // 128, r.id))
        return mes
    
    def walk(self, avoid_mine = False, safe = False, dest = False):
        #safe mode not implemented yet
        if dest == False:
            dest = self.dest[0]
        
        def dirns(radi):
            res = []
            dx = 0
            dy = 0
            while dx**2 <= radi:
                while dy**2 + dx**2 <= radi:
                    res.append((dx,dy))
                    if dx != 0:
                        res.append((-dx,dy))
                    if dy != 0:
                        res.append((dx,-dy))
                    if dx != 0 and dy != 0:
                        res.append((-dx,-dy))
                    dy+=1
                dy = 0
                dx += 1
            return res
        x,y = self.map_size
        me_x = self.me.x
        me_y = self.me.y
        mp = self.level_map
        
        def check_mine(x_pos, y_pos):
            #True means it's passalbe
            #False means there is mine
            if self.karbonite_map[y_pos][x_pos]:
                return False
            if self.fuel_map[y_pos][x_pos]:
                return False
            return True
        
        speed = SPECS['UNITS'][self.me.unit]['SPEED']
        dirn = dirns(speed)
        available_step = []
        for dx, dy in dirn:
            t_x = me_x + dx
            t_y = me_y + dy
            if mp[t_y][t_x] != False and mp[t_y][t_x] != True:
                if (not avoid_mine) or check_mine(t_x,t_y):
                    if self.test_Valid_Square((dx,dy)):
                        available_step.append((dx,dy,1000*mp[t_y][t_x]+(dest[0]-t_x)**2 + (dest[1]-t_y)**2))
        self.sort_list(available_step)
        
        move = (available_step[0][0],available_step[0][1])
        return move
    
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
            else:
                #If we have time, we should re-write victory message
                return True
    

    def turn(self):
        self.step += 1
        self.global_turn += 1
        if (self.me.unit == 0) and (self.step % 100 == 0):
            self.log("--------------------------------------------------------")
        if self.step == 0:
            self.set_map_size()
            self.set_symmetry()
            self.temp_map = []
            for y in range(self.map_size[1]):
                self.temp_map.append(self.map[y][0:])
            
            if (self.me.unit >= 2):
                self.receive_initiation()
            elif (self.me.unit == 3):
                self.mode = 2
                #self.log("bingo")
            elif (self.me.unit == 1):
                self.mode = 0
            else: #castle determine mode
                self.castle_num = len(self.get_visible_robots())
                if (self.castle_num == 1):
                    self.mode = 1
                elif (self.castle_num == 3):
                    self.mode = 0
                else:
                    mine_count = 0
                    for x in range(self.map_size[0]):
                        for y in range(self.map_size[1]):
                            if (self.karbonite_map[y][x]) or (self.fuel_map[y][x]):
                                mine_count += 1
                    if (mine_count < 18):
                        self.mode = 1
                    else:
                        self.mode = 0
        if self.me.unit == 3:
            self.mode = 2
        if (self.mode == 0):
            return self.turn1()
        elif (self.mode == 1):
            return self.turn2()
        elif (self.mode == 2):
            return self.turn3()

    def turn1(self):
        self.stop_building = False
        if (self.me.unit == 0):
            self.processing_c_talk()
            enemies = self.identify_attackable_enemies()
            if (len(enemies) > 0):
                return self.attack(enemies[0].x - self.me.x, enemies[0].y - self.me.y)
            if self.step == 0:
                self.castle_num = len(self.get_visible_robots())
                self.find_nearby_karbonite_mine()
                self.artillary_lattice_initialize()
                self.castle_list.append((self.me.id, self.me.x, self.me.y))
                self.castle_talk(self.me.x)
                return None
            if self.step == 1:
                self.castle_talk(self.me.y)
                return None
            if self.step == 2:
                self.find_mine_cluster()
            self.replenish_nearby_pilgrim()
            ##self.log(self.nearby_karbonite_mine)
            if self.flag == True:
                self.broadcast(0,0,self.dest[1][1][0],self.dest[1][1][1])
                self.flag = 10
            
            if (self.step > 10) and (self.flag != 10):
                if self.crusader_count * self.castle_num <= 1: #a very primitive condition for building crusaders
                    #suggestion: build pilgrams first; and let one crusader attack no less than 5 mines.
                    
                    if (self.karbonite >= 15) and (self.fuel >= 100):
                        self.crusader_count += 1
                        if len(self.dest[1]) != 0:
                            self.broadcast(2,len(self.dest[1]),self.dest[1][0][0],self.dest[1][0][1])
                            if len(self.dest[1]) == 2:
                                self.flag = True
                        else:
                            self.broadcast(self.mode,0,10,10)
                        for d in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                            if self.test_Valid_Square(d):
                                return self.build_unit(3, d[0], d[1])
            else:
                self.flag = False
            
            if (self.karbonite > 11) and (self.fuel > 60) and not self.stop_building:
                if len(self.nearby_karbonite_mine) > 0:
                    dest = self.nearby_karbonite_mine[0]
                    rel = (self.sign(dest[0] - self.me.x), self.sign(dest[1] - self.me.y))
                    if self.test_Valid_Square(rel):
                        self.broadcast(self.mode,0,dest[0],dest[1])
                        self.nearby_karbonite_mine = self.nearby_karbonite_mine[1:]
                        return self.build_unit(2, rel[0], rel[1])
                    else:
                        for (i,j) in self.dirns(2):
                            if self.test_Valid_Square((i,j)):
                                rel = (i,j)
                                self.broadcast(self.mode,0,dest[0],dest[1])
                                self.nearby_karbonite_mine = self.nearby_karbonite_mine[1:]
                                return self.build_unit(2, rel[0], rel[1])
                elif (len(self.far_mine_list) > 0) and (self.step % 3 == 0) and (self.fuel > 100):
                    dest = self.far_mine_list[0]
                    rel = (self.sign(dest[0] - self.me.x), self.sign(dest[1] - self.me.y))
                    if self.test_Valid_Square(rel):
                        self.broadcast(self.mode,1,dest[0],dest[1])
                        self.far_mine_list = self.far_mine_list[1:]
                        return self.build_unit(2, rel[0], rel[1])
                    else:
                        for (i,j) in self.dirns(2):
                            if self.test_Valid_Square((i,j)) and ((i != 0) or (j != 0)):
                                self.broadcast(self.mode,1,dest[0],dest[1])
                                self.far_mine_list = self.far_mine_list[1:]
                                return self.build_unit(2,i,j)
                elif (len(self.nearby_fuel_mine) > 0) and (self.step % 3 == 1):
                    dest = self.nearby_fuel_mine[0]
                    rel = (self.sign(dest[0] - self.me.x), self.sign(dest[1] - self.me.y))
                    if self.test_Valid_Square(rel):
                        self.broadcast(self.mode,0,dest[0],dest[1])
                        self.nearby_fuel_mine = self.nearby_fuel_mine[1:]
                        return self.build_unit(2, rel[0], rel[1])
                    else:
                        for (i,j) in self.dirns(2):
                            if self.test_Valid_Square((i,j)):
                                rel = (i,j)
                                self.broadcast(self.mode,0,dest[0],dest[1])
                                self.nearby_fuel_mine = self.nearby_fuel_mine[1:]
                                return self.build_unit(2, rel[0], rel[1])
            if (self.fuel > 150) and (self.karbonite > 30) and not self.stop_building:
                dest = (self.artillary_lattice[0][0], self.artillary_lattice[0][1])
                rel = (self.sign(dest[0] - self.me.x), self.sign(dest[1] - self.me.y))
                if self.test_Valid_Square(rel):
                    self.broadcast(self.mode,0,dest[0],dest[1])
                    self.artillary_lattice = self.artillary_lattice[1:]
                    return self.build_unit(4, rel[0], rel[1])
                else:
                    for (i,j) in self.dirns(2):
                        if self.test_Valid_Square((i,j)):
                            rel = (i,j)
                            self.broadcast(self.mode,0,dest[0],dest[1])
                            self.artillary_lattice = self.artillary_lattice[1:]
                            return self.build_unit(4, rel[0], rel[1])


        if (self.me.unit == 1):
            if (self.step == 0):
                self.find_nearby_karbonite_mine()
            else:
                if (self.karbonite > 11) and (self.fuel > 60) and not self.stop_building:
                    if len(self.nearby_karbonite_mine) > 0:
                        dest = self.nearby_karbonite_mine[0]
                        rel = (self.sign(dest[0] - self.me.x), self.sign(dest[1] - self.me.y))
                        while not self.test_Valid_Square((dest[0] - self.me.x, dest[1] - self.me.y)):
                            self.nearby_karbonite_mine = self.nearby_karbonite_mine[1:]
                            dest = self.nearby_karbonite_mine[0]
                            rel = (self.sign(dest[0] - self.me.x), self.sign(dest[1] - self.me.y))
                        if self.test_Valid_Square(rel):
                            self.broadcast(self.mode,0,dest[0],dest[1])
                            self.nearby_karbonite_mine = self.nearby_karbonite_mine[1:]
                            return self.build_unit(2, rel[0], rel[1])
                        else:
                            for (i,j) in self.dirns(2):
                                if self.test_Valid_Square((i,j)):
                                    rel = (i,j)
                                    self.broadcast(self.mode,0,dest[0],dest[1])
                                    self.nearby_karbonite_mine = self.nearby_karbonite_mine[1:]
                                    return self.build_unit(2, rel[0], rel[1])
                    elif len(self.nearby_fuel_mine) > 0:
                        dest = self.nearby_fuel_mine[0]
                        rel = (self.sign(dest[0] - self.me.x), self.sign(dest[1] - self.me.y))
                        while not self.test_Valid_Square((dest[0] - self.me.x, dest[1] - self.me.y)):
                            self.nearby_fuel_mine = self.nearby_fuel_mine[1:]
                            dest = self.nearby_fuel_mine[0]
                            rel = (self.sign(dest[0] - self.me.x), self.sign(dest[1] - self.me.y))
                        if self.test_Valid_Square(rel):
                            self.broadcast(self.mode,0,dest[0],dest[1])
                            self.nearby_fuel_mine = self.nearby_fuel_mine[1:]
                            return self.build_unit(2, rel[0], rel[1])
                        else:
                            for (i,j) in self.dirns(2):
                                if self.test_Valid_Square((i,j)):
                                    rel = (i,j)
                                    self.broadcast(self.mode,0,dest[0],dest[1])
                                    self.nearby_fuel_mine = self.nearby_fuel_mine[1:]
                                    return self.build_unit(2, rel[0], rel[1])


        if (self.me.unit == 2) and (self.step == 0):
            self.set_home()
            mes = self.receive_initiation()
            self.dest = mes
            if (self.code == 0):
                self.BFS(self.dest, 0, 4)
            else:
                self.BFS(self.dest, 0, 2)
            return None

        if (self.me.unit == 2) and (self.code == 0):#pilgrims mining move
            if ((self.me.x - self.home[0]) ** 2 + (self.me.y - self.home[1]) ** 2 <= 2) and ((self.me.karbonite >= 20) or (self.me.fuel >= 100)):
                self.BFS(self.dest, 0, 4)
                return self.give(self.home[0] - self.me.x, self.home[1] - self.me.y, self.me.karbonite, self.me.fuel)
            if (self.me.x == self.dest[0]) and (self.me.y == self.dest[1]):
                if ((self.me.karbonite < 20) and (self.me.fuel < 100)):
                    self.still = 0
                    return self.mine()
                else:
                    self.BFS(self.home, 2, 4)
            if (self.fuel < 100):
                return None
            move = (0,0)
            optimal = self.level_map[self.me.y][self.me.x] + 1
            for (i,j) in self.dirns(4):
                if self.test_Valid_Square((i,j)) and (self.level_map[j + self.me.y][i + self.me.x] < optimal):
                    move = (i,j)
                    optimal = self.level_map[j + self.me.y][i + self.me.x]
            if (move[0] != 0) or (move[1] != 0) and (optimal <= self.level_map[self.me.y][self.me.x]):
                self.still = 0
                return self.move(move[0], move[1])
            self.still += 1
            if (self.still >= 5):
                self.dest = self.set_opponent_castle(self.home[0], self.home[1])

        if (self.me.unit == 2) and (self.code == 1): #far pilgrims
            if (self.fuel < 100):
                return None
            if (self.me.x - self.dest[0]) ** 2 + (self.me.y - self.dest[1]) ** 2 <= 2:
                castled = False
                for r in self.get_visible_robots():
                    if (r.unit == 1) and (r.team == self.me.team) and ((self.me.x - r.x) ** 2 + (self.me.y - r.y) ** 2 <= 9):
                        self.home = (r.x, r.y)
                        self.code = 0
                        self.find_dest()
                        self.BFS(self.dest, 0, 2)
                        castled = True
                        move = (0,0)
                        optimal = self.level_map[self.me.y][self.me.x]
                        for (i,j) in self.dirns(4):
                            if self.test_Valid_Square((i,j)) and (self.level_map[j + self.me.y][i + self.me.x] < optimal):
                                move = (i,j)
                                optimal = self.level_map[j + self.me.y][i + self.me.x]
                        if ((move[0] != 0) or (move[1] != 0)) and (optimal <= self.level_map[self.me.y][self.me.x]):
                            return self.move(move[0], move[1])
                if (not castled):
                    if (self.fuel > 200) and (self.karbonite > 50):
                        for r in self.dirns(2):
                            if self.test_Valid_Square(r):
                                return self.build_unit(1, r[0], r[1])
                    else:
                        self.castle_talk(255) #report attempted church building
            if (self.me.x == self.dest[0]) and (self.me.y == self.dest[1]):
                return self.mine()
            else:
                move = (0,0)
                optimal = 9999
                for (i,j) in self.dirns(2):
                    if self.test_Valid_Square((i,j)) and (self.level_map[j + self.me.y][i + self.me.x] <= optimal):
                        move = (i,j)
                        optimal = self.level_map[j + self.me.y][i + self.me.x]
                if ((move[0] != 0) or (move[1] != 0)) and (optimal <= self.level_map[self.me.y][self.me.x]):
                    return self.move(move[0], move[1])

        if (self.me.unit == 4): #TODO: charge after 500 turns
            enemies = self.identify_attackable_enemies()
            if (self.step == 0):
                self.set_home()
                mes = self.receive_initiation()
                self.dest = (mes[0],mes[1])
            if (self.global_turn > 399) and (self.global_turn % 100 == 0):
                self.dest = self.set_opponent_castle(self.home[0], self.home[1])
            if (self.step % 3 == 0):
                self.BFS(self.dest, 0, 4)
            if (len(enemies) > 0):
                return self.attack(enemies[0].x - self.me.x, enemies[0].y - self.me.y)
            if (self.step == 0):
                return None
            if (self.me.x == self.dest[0]) and (self.me.y == self.dest[1]):
                return None
            if ((self.me.x - self.dest[0]) ** 2 + (self.me.y - self.dest[1]) ** 2 <= 4):
                return self.move(self.dest[0] - self.me.x, self.dest[1] - self.me.y)
            else:
                move = (0,0)
                optimal = 9999
                for (i,j) in self.dirns(4):
                    if self.test_Valid_Square((i,j)) and (self.level_map[j + self.me.y][i + self.me.x] <= optimal):
                        move = (i,j)
                        optimal = self.level_map[j + self.me.y][i + self.me.x]
                if ((move[0] != 0) or (move[1] != 0)) and (optimal < self.level_map[self.me.y][self.me.x]) and (self.fuel > 100):
                    return self.move(move[0], move[1])
                elif (self.fuel > 100):
                    move = (0,0)
                    optimal = 0
                    x = self.me.x
                    y = self.me.y
                    hx = self.home[0]
                    hy = self.home[1]
                    for (i,j) in self.dirns(2):
                        if self.test_Valid_Square((i,j)) and ((hx - i - x) ** 2 + (hy - j - y) ** 2 > optimal):
                            move = (i,j)
                            optimal = (hx - i - x) ** 2 + (hy - j - y) ** 2
                    if (move[0] != 0) or (move[1] != 0):
                        return self.move(move[0], move[1])
    
    def turn2(self):
        #0.2.3 preacher rush
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
                return None
            
            if self.step == 1:
                self.castle_talk(self.me.y)
            self.processing_c_talk()
            enemies = self.identify_attackable_enemies()
            if (len(enemies) > 0):
                return self.attack(enemies[0].x - self.me.x, enemies[0].y - self.me.y)
            
            if (self.count * self.castle_num <= 2): #very primitive pilgrim building
                self.count += 1
                d = self.karbonite_pilgrim_direction_list[0]
                if self.test_Valid_Square(d):
                    self.karbonite_pilgrim_direction_list = self.karbonite_pilgrim_direction_list[1:]
                    self.broadcast(self.mode,0,self.karbo_list[0][0],self.karbo_list[0][1])
                    self.karbo_list = self.karbo_list[1:]
                    return self.build_unit(2, d[0], d[1])
                else:
                    for d in [(1,1),(1,-1),(-1,1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)]:
                        if self.test_Valid_Square(d):
                            self.karbonite_pilgrim_direction_list = self.karbonite_pilgrim_direction_list[1:]
                            self.broadcast(self.mode,0,self.karbo_list[0][0],self.karbo_list[0][1])                            
                            self.karbo_list = self.karbo_list[1:]
                            return self.build_unit(2, d[0], d[1])
            elif ((self.fuel >= 60) and (self.karbonite >= 31) and (self.step >= 3)): #Tank attack!
                if len(self.dest[0]) >= 1:
                    if (len(self.dest) >= 2) and (len(self.dest[1]) != 0):
                        self.broadcast(self.mode, 0, self.dest[1][0][0], self.dest[1][0][1]) #TODO: change this
                    else:
                        self.broadcast(self.mode, 0, 0, 0)
                else:
                    self.broadcast(self.mode, 0, self.dest[1][0][0], self.dest[1][0][1])
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
            
                self.BFS(self.dest[0],0)
            if (self.me.x == self.dest[0][0]) and (self.me.y == self.dest[0][1]):
                if (self.me.fuel < 100) and (self.me.karbonite < 20):
                    return self.mine()
                elif (self.me.x - self.home[0])**2 + (self.me.y - self.home[1])**2 < 4:
                    return self.give(self.home[0] - self.me.x, self.home[1] - self.me.y, self.me.karbonite, self.me.fuel)
                else:
                    self.BFS(self.home, 3)
            if (self.me.x - self.home[0])**2 + (self.me.y - self.home[1])**2 < 4:
                if (self.me.fuel >= 100) or (self.me.karbonite >= 20):
                    self.BFS(self.dest[0],0)
                    return self.give(self.home[0] - self.me.x, self.home[1] - self.me.y, self.me.karbonite, self.me.fuel)
            if self.level_map[self.me.y][self.me.x] != 2:
                move = self.walk()
                return self.move(move[0],move[1])
        
        if self.me.unit == 5:
            if self.step == 0:
                self.set_home()
                mes = self.receive_initiation()
                if self.code == 0:
                    self.dest.append(self.set_opponent_castle(self.home[0],self.home[1]))
                self.dest.append((mes[0],mes[1]))
                self.BFS(self.dest[0],16) 
            targets = self.identify_attackable_enemies()
            if len(targets) != 0:
                return self.attack(targets[0].x - self.me.x, targets[0].y - self.me.y)
            elif (self.dest[0][0] - self.me.x)**2 + (self.dest[0][1] - self.me.y)**2 <= 16:
                self.dest[0] = self.dest[1]
                self.BFS(self.dest[0],16)
            else:
                move = self.walk()
                return self.move(move[0],move[1])
    
    def turn3(self):
        if self.me.unit == 0:
            if self.flag == True:
                self.broadcast(self.mode,0,self.dest[1][1][0],self.dest[1][1][1])
                self.flag = 10
            if self.step == 0:
                self.castle_num = len(self.get_visible_robots())
                self.castle_talk(self.me.x)
                self.dest = [[],[]]
                self.dest[0] = self.set_opponent_castle(self.me.x,self.me.y)
            if self.step == 1:
                self.castle_talk(self.me.y)
            self.processing_c_talk()
            enemies = self.identify_attackable_enemies()
            if (len(enemies) > 0):
                return self.attack(enemies[0][0], enemies[0][1])
            if self.step > 2 and (self.flag != 10):
                if self.crusader_count * self.castle_num <= 1: #a very primitive condition for building crusaders
                    #suggestion: build pilgrams first; and let one crusader attack no less than 5 mines.
                    self.crusader_count += 1
                    if (self.karbonite >= 15) and (self.fuel >= 100):
                        if len(self.dest[1]) != 0:
                            self.broadcast(0,len(self.dest[1]),self.dest[1][0][0],self.dest[1][0][1])
                            if len(self.dest[1]) == 2:
                                self.flag = True
                        else:
                            self.broadcast(self.mode,0,10,10)
                        for d in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                            if self.test_Valid_Square(d):
                                return self.build_unit(3, d[0], d[1])
            else:
               self.flag = False
                        
                  
        if self.me.unit == 3: #crusader targeting at mines
            if self.step == 0:
                mes = self.receive_initiation()
                self.mode = 2
                self.code = mes[3]
                if self.code != 0:
                    self.dest.append((mes[0],mes[1]))
                self.set_home()
                self.dest.append(self.set_opponent_castle(self.home[0],self.home[1]))
            if self.step == 1:
                if self.code == 2:
                    mes = self.receive_initiation()
                    self.dest.append((mes[0],mes[1]))
                self.mark_dangerous_regions(self.dest)
                self.generate_destinations()#self.dest will be replaced by a bunch of mines
            targets = self.identify_attackable_enemies()
            if len(targets) != 0:
                return self.attack(targets[0].x - self.me.x, targets[0].y - self.me.y)
            pilgram = self.identify_pilgram()
            
            if self.step >= 1:
                if pilgram != False:
                    if self.BFS(pilgram, 16):
                        self.flag = False
                        move = self.walk(False, False, pilgram)
                        return self.move(move[0],move[1])
                elif self.flag:
                    move = self.walk()
                    if (self.me.x - self.dest[0][0])**2 + (self.me.y - self.dest[0][1])**2 <= 49:
                        self.flag = False
                    return self.move(move[0],move[1])
                else:
                    i = random.choice(range(len(self.dest)))
                    temp = self.dest[i]
                    self.dest[i] = self.dest[0]
                    self.dest[0] = temp
                    self.flag = True
                    if self.BFS(self.dest[0],49):
                        move = self.walk()
                        return self.move(move[0],move[1])
                    else:
                        self.flag = False
        
            
robot = MyRobot()
