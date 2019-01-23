from battlecode import BCAbstractRobot, SPECS
import battlecode as bc
import random

# Only enable these if you really need them.
#__pragma__('iconv')
#__pragma__('tconv')
#__pragma__('opov')

#Version: 0.3.0 debugging
#Last Edit: Shengtong Zhang
#Description: This bot will:
#1. build pilgrims to mine karbo/fuel and build preacher to attack the opponent's castle.
#2. Enable every preacher to carry two positions of enemy's castles; preachers will turn to second location when finished
#3. In case of unexpected path-finding mistakes, preachers will turn back home
#4. Uses a less stable, yet clock-suitable version of DFS proposed by Deng.
#5. (Experimental) detect large mines & formations
class MyRobot(BCAbstractRobot):
    def __init__(self):
        BCAbstractRobot.__init__(self)
        self.castle_num = 0
        self.step = -1 # turn count
        self.dest = [] #default as invalid
        self.home = (0,0) #for handing in resources
        self.map_size = (0,0)
        self.map_symmetry = False #V means a[i][j] = a[t - i][j], H means otherwise
        self.mode = 0
        #castles: 0 for default, 1 for mining-oriented
        #miners: 0 for karbonite close miners, 1 for far miners, 2 for team-leaders
        #preachers: 0 for default, 1 for formation
        self.code = 0 #0: home oppo first, then dest in the message; 1: direct to the mes.
        self.castle = None #the castle object
        self.castle_list = [] #format: [id, x, y]
        self.fuel_list = [] #list of locs of fuel, sorted by dist
        self.karbo_list = [] #list of locs of karbo, sorted by dist
        self.count = 0 #Set up a count for building units
        self.route = []
        self.forward_route = [] #For pilgram only
        self.back_route = []
        self.karbonite_pilgrim_direction_list = [] #optimization for neighboring mines
        self.fuel_pilgrim_direction_list = []
        self.pilgrim_quota = 3 #maximal number of pilgrims built by any unit
        self.pilgrim_count = 0 #number of pilgrims built
        self.total_unit_count = 0 #total number of units
        self.still = 0 #In case of unexpected bugs
        self.large_mine = 7 #how much is needed for a big mine
        self.mine_dest = [] #coordinate of large mines
        self.build_queue = [] #used in formation
        self.team_expense = (0,0) #stuff needed to build team
        self.build_index = 0 #for castle to visit build_queue
        self.teammates = [] #who are my teammates
        self.team_size = 0 #provided by castle
        self.team_leader = None #the leader of the team, the first to be built
        self.team_silence = 0
        self.level_map = []

    def receive_initiation(self): #bug free
        for r in self.get_visible_robots():
            if (self.is_radioing(r) and (r.signal_radius <= 2) and (r.signal != 0) and (r.unit == 0)):
                self.castle = r
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

    def set_team_leader(self): #set team leader for regular teammates
        for r in self.get_visible_robots():
            if (self.is_radioing(r) and (r.unit != 0)):
                mes = r.signal
                if (mes == 33300):
                    self.team_leader = r

    def team_turn(self):
        if (self.step == 0):
            self.set_team_leader()
            self.log(self.team_leader)
        r = self.team_leader
        if (self.mode == 1): #not the leader
            m = 0
            if (self.is_radioing(r)):
                m = r.signal
                x = r.x
                y = r.y
                self.team_silence = 0
            else: #team leader is dead?
                self.team_silence += 1
                if (self.team_silence > 3):
                    self.mode = 0
                    self.dest.append(self.set_opponent_castle(self.home[0], self.home[1]))
            #receive radio update, determine action
            action = m // (400) #0: move 1: attack 33: don't do anything
            m = m % 400
            rel_x = m // 20 - 10
            rel_y = m % 20 - 10
            if (action == 33):
                return None
            if (action == 0):
                for s in self.get_visible_robots():
                    if (self.is_visible(s) and (s.team != self.me.team)):
                        self.signal(232300 + (s.x - self.me.x) * 10 + (s.y - self.me.y), (self.me.x - x)**2 + (self.me.y - y)**2) #teammates to leader, not implemented
                        if ((s.x - self.me.x) ** 2 + (s.y - self.me.y) ** 2 <= SPECS["UNITS"][self.me.unit]["ATTACK_RADIUS"][1]):
                            return self.attack(s.x - self.me.x, s.y - self.me.y)
                self.BFS((x,y), 1, 4)
                level_min = 999
                d0 = (0,0)
                for d in self.dirns(4):
                    if (self.level_map[d[1]][d[0]] != True) and (self.level_map[d[1]][d[0]] < level_min):
                        d0 = d
                        level_min = self.level_map[d[1]][d[0]]
                return self.move(d0[0], d0[1])
            if (action == 1):
                enemy_x = rel_x + x - self.me.x
                enemy_y = rel_y + y - self.me.y
                dx = self.sign(enemy_x)
                dy = self.sign(enemy_y)
                if (enemy_x ** 2 + enemy_y **2 < SPECS["UNITS"][self.me.unit]["ATTACK_RADIUS"][0]):
                    return self.move(-dx, -dy)
                elif (enemy_x ** 2 + enemy_y **2 <= SPECS["UNITS"][self.me.unit]["ATTACK_RADIUS"][1]):
                    return self.attack(enemy_x, enemy_y)
                else:
                    self.BFS((x,y), SPECS["UNITS"][self.me.unit]["ATTACK_RADIUS"][1], 4)
                    level_min = 999
                    d0 = (0,0)
                    for d in self.dirns(4):
                        if (self.level_map[d[1]][d[0]] != True) and (self.level_map[d[1]][d[0]] < level_min):
                            d0 = d
                            level_min = self.level_map[d[1]][d[0]]
                    return self.move(d0[0], d0[1])

    def team_leader_turn(self):
        if (False): #somebody delete this!
            pass
        else: #team_leader
            for r in self.teammates: #teammates to leader channel, unimplemented
                pass
            if (self.step == 0):  #initial BFS
                self.dest.append(self.set_opponent_castle(self.home[0], self.home[1]))
                self.BFS(self.dest[0], 0, 4)
                self.log('pass')
                return None
            if (len(self.teammates) < self.team_size): #team not ready
                self.signal(13200, 9)
                r = self.castle
                if (self.is_radioing(r)):
                    mes = r.signal
                    if (mes % 4 == 1): #initialization radio
                        for r in self.get_visible_robots():
                            if (r.turn == 0): #just built; append to teammates
                                 self.teammates.append(r)
            else:
                if (self.fuel < 30): #not enough fuel, stop
                    self.signal(13200, 25)
                    return None
                else:
                    enemies = self.identify_attackable_enemies()
                    if (len(enemies) > 0): #attack enemies
                        enemy = enemies[0]
                        enemy_x = enemy.x - self.me.x
                        enemy_y = enemy.y - self.me.y
                        self.signal(400 + (enemy_x + 10) * 20 + enemy_y + 10, 25) #there is bug here
                        dx = self.sign(enemy_x)
                        dy = self.sign(enemy_y) #running away, not implemented
                    else:
                        #move
                        level_min = 999
                        d0 = (0,0)
                        self.signal(0, 25)
                        for d in self.dirns(4):
                            if (self.level_map[d[1]][d[0]] != True) and (self.level_map[d[1]][d[0]] < level_min):
                                d0 = d
                                level_min = self.level_map[d[1]][d[0]]
                        return self.move(d0[0], d0[1])

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
    def BFS(self, dest, aim, speed):
        #aim: the scale of the dest.
        #e.g. if the goal is to attack the object at dest, then set aim = attack_range
        #if the goal is to hand in resources, then set aim = 2
        #check if self is within aim of dest!!!
        mp = []
        sf_map = self.map
        x,y = self.map_size
        d_x, d_y = dest
        me_x = self.me.x
        me_y = self.me.y

        for i in range(y):
            mp.append(sf_map[i][0:]+3*[False])
        mp.append((3+x)*[False])
        mp.append((3+x)*[False])
        mp.append((3+x)*[False])
        scale = self.dirns(aim)
        stack = []
        for (dx,dy) in scale:
            if mp[d_y+dy][d_x+dx] == True:
                mp[d_y+dy][d_x+dx] = 0
                stack.append((d_x+dx, d_y+dy))
        dirn = self.dirns(speed)
        count = 0
        mp[me_y][me_x] = "S"
        while len(stack) > count:
            (c_x,c_y) = stack[count]
            level = mp[c_y][c_x] + 1
            for (dx,dy) in dirn:
                t_x = c_x+dx
                t_y = c_y+dy
                if mp[t_y][t_x] == True:
                    mp[t_y][t_x] = level
                    stack.append((t_x,t_y))
                elif mp[t_y][t_x] == "S":
                    mp[t_y][t_x] = level
                    self.level_map = mp
                    return True
            count += 1
        return False

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

    def find_route(self, dest, avoid_mine = True, aim = 16): #in combat maneuver, only mark grids inside sight range; bug free #The avoid_mine parameter is added to avoid working miners
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
        for r in self.get_visible_robots():
            new_map[r.y][r.x] = False
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
    def set_large_mine(self):
        mine_list = self.fuel_list + self.karbo_list
        mine_dest = []
        for d in mine_list:
            i = d[0]
            j = d[1]
            mine_found = 0
            for k in range(-4, 5):
                for l in range(-4, 5):
                    if (self.test_Square_In_Bound(i + k, j + l) and (self.karbonite_map[j + l][i + k] or self.fuel_map[j + l][i + k])):
                        mine_found += 1
                        if (self.karbonite_map[j + l][i + k]):
                              mine_found += 1
            if (mine_found >= self.large_mine):
                mine_dest.append((i,j,(i - self.me.x) ** 2 + (j - self.me.y) ** 2))
        self.sort_list(mine_dest)
        self.mine_dest = mine_dest
        return (len(self.mine_dest) > 0)

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
        if ((i[0] == 0) and (i[1] == 0)):
            return True
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

    def set_mine(self):
        for x in range(self.map_size[0]):  #TODO: clean this mess
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

    def turn(self):
        self.step += 1
        if self.step == 0:
            self.set_map_size()
            self.set_symmetry()
            self.build_queue = [2,2,2,2]
        if (self.me.unit == 0) and (self.get_visible_robots()[0].id == self.me.id):
            if self.step == 0:
                self.castle_num = len(self.get_visible_robots())
                self.set_mine()
                mine_found = self.set_large_mine()
                if (mine_found):
                    self.mode = 1 #mining-oriented mode
                    self.pilgrim_quota *= 2
                else:
                    self.mode = 0 #attack-oriented mode
                self.castle_talk(self.me.x)
                self.dest = []
                self.dest.append(self.set_opponent_castle(self.me.x,self.me.y))
            if self.step == 1:
                self.castle_talk(self.me.y)
            self.processing_c_talk()

            if (self.build_index < len(self.build_queue)): #build stuff
                unit = self.build_queue[self.build_index]
                d = (0,0)
                for e in [(1,1),(1,-1),(-1,1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)]:
                    if self.test_Valid_Square(e):
                        d = e
                if (self.build_index == 0):
                    self.broadcast(2,len(self.build_queue) - 1,0,0) #TODO
                else:
                    self.broadcast(1,0,0,0)
                if (d[0] != 0) or (d[1] != 0):
                    self.build_index += 1
                return self.build_unit(unit, d[0], d[1])

            elif ((self.fuel >= 60) and (self.karbonite >= 11) and (self.pilgrim_count * self.castle_num <= self.pilgrim_quota) and (self.total_unit_count % 2 == 0)): #very primitive pilgrim building
                far_miner = (self.mode == 1) and (self.pilgrim_count % 2 == 1)
                self.pilgrim_count += 1
                self.total_unit_count += 1
                d = self.karbonite_pilgrim_direction_list[0]
                if (far_miner == False):
                    self.karbonite_pilgrim_direction_list = self.karbonite_pilgrim_direction_list[1:]
                if not (self.test_Valid_Square(d)):
                    for e in [(1,1),(1,-1),(-1,1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)]:
                        if self.test_Valid_Square(e):
                            d = e
                if (far_miner):
                    self.broadcast(0,0,self.mine_dest[0][0], self.mine_dest[0][1]) #far_miners
                else:
                    self.broadcast(0,0,self.karbo_list[0][0],self.karbo_list[0][1])
                    self.karbo_list = self.karbo_list[1:]
                return self.build_unit(2, d[0], d[1])

            elif ((self.fuel >= 60) and (self.karbonite >= 31)): #Tank attack!
                if len(self.dest[0]) >= 1:
                    if (len(self.dest) >= 2) and (len(self.dest[1]) != 0):
                        self.broadcast(0, 0, self.dest[1][0][0], self.dest[1][0][1]) #TODO: change this
                    else:
                        self.broadcast(0, 0, 0, 0)
                else:
                    self.broadcast(0, 0, self.dest[1][0][0], self.dest[1][0][1])
                for d in [(1,1),(1,-1),(-1,1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)]:
                    if self.test_Valid_Square(d):
                        self.total_unit_count += 1
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

        if self.me.unit == 2: #crusader move; bug free
            if self.step == 0:
                self.set_home()
                mes = self.receive_initiation()
            if (self.mode == 1):
                return self.team_turn()
            elif (self.mode == 2):
                self.team_size = self.code + 1
                self.teammates.append(self.me)
                return self.team_leader_turn()
            else:
                self.dest.append((mes[0],mes[1]))
                self.find_route(self.dest[0], aim = 0)
                self.forward_route = self.route[0:]
                for i in range(len(self.route)):
                    self.back_route.append((-self.route[len(self.route) - 1 - i][0],-self.route[len(self.route) - 1 - i][1]))
            if len(self.route) > 0 and (self.fuel > 20):
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

        if self.me.unit >= 3: #combat unit  move; bug free
            self.log(self.dest)
            if self.step == 0:
                self.set_home()
                mes = self.receive_initiation()
                if self.code == 0:
                    self.dest.append(self.set_opponent_castle(self.home[0],self.home[1]))
                self.dest.append((mes[0],mes[1]))
                if (self.mode == 1):
                    self.set_team_leader()
                return None
            if (self.mode == 1):
                return self.team_turn()
            targets = self.identify_attackable_enemies()
            if len(targets) != 0:
                return self.attack(targets[0].x - self.me.x, targets[0].y - self.me.y)
            elif (self.fuel < 50):
                return None
            elif (len(self.route) > 0) and (self.fuel > 20):
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
                        self.dest = [(self.home[0] + 2, self.home[1] + 2)]
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
