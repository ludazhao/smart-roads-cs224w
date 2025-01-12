import snap
import Queue
import copy
import math
from geopy.distance import vincenty
import random
import numpy

#Elena did this
#def getDistance(coor1, coor2):
#    return math.sqrt(pow(coor1[0] - coor2[0], 2) + pow(coor1[1] - coor2[1], 2))


#Class for traffic model.
class TrafficModel:

    # graph: snappy graph, node_attr: a dict of n1 to node coordinates(lat, long), edge_typo, edge_speed: a dict of (n1, n2) to edge properties, n_to_e: a link from (n1, n2) to a list of edge ids(to preserve which edges are part of the same road)
    # the only changing variables to calculate our trafficmodel is self.e_flow and self.e_time. All other variables are constant
    def __init__(self, graph, better_graph, node_attr, edge_typo, edge_speed, edge_lanes, n_to_e, init_pairs=[]):
        self.graph2 = graph
        self.g = better_graph
        self.node_coor = node_attr #the coordinate of each node
        self.e_type = edge_typo #the typology of each edge
        self.e_dist = {} #the distance for each edge
        self.e_speed = edge_speed # the maximum allowed speed of each edge.
        self.e_lanes = edge_lanes # the number of lanes of each road
        self.num_nodes = graph.GetNodes()
        self.capacity = {}
        self.init_pairs = init_pairs
        print self.num_nodes

        #get maximum speed for all edge
        #residential: 15
        for e in self.e_speed:
            e_type = self.e_type[e]
            if self.e_speed[e] == 'N/A':
                if e_type == 'residential':
                    self.e_speed[e] = 20
                elif e_type == 'tertiary':
                    self.e_speed[e] = 25
                elif e_type == 'secondary':
                    self.e_speed[e] = 25
                elif e_type == 'primary':
                    self.e_speed[e] = 35
                elif e_type == 'motorway' or e_type == 'trunk':
                    self.e_speed[e] = 55
                else:
                    self.e_speed[e] = 25
            else:
                self.e_speed[e] = int(self.e_speed[e].replace("mph", ""))
            if self.e_lanes[e] != 'N/A' and self.e_lanes[e] != "0":
                self.capacity[e] = int(self.e_lanes[e])
            else:
                if e_type == 'residential':
                    self.capacity[e] = 1
                elif e_type == 'tertiary':
                    self.capacity[e] = 2
                elif e_type == 'secondary':
                    self.capacity[e] = 2
                elif e_type == 'primary':
                    self.capacity[e] = 3
                elif e_type == 'motorway' or e_type == 'trunk':
                    self.capacity[e] = 4
                else:
                    self.capacity[e] = 1


        #calculate distance for each edge(loop over e_type since it contains all edges)
        for e in self.e_type:
            coor1 = self.node_coor[e[0]]
            coor2 = self.node_coor[e[1]]

            dist2 = vincenty(coor1, coor2).miles
            self.e_dist[(int(e[0]), int(e[1]))] = dist2

        #initializae the # of cars to be 0 on all edges
        self.e_flow = {}
        for e in self.e_type:
            self.e_flow[(int(e[0]), int(e[1]))] = 0

        self.e_time = {} #the time needed to traverse an edge. Used as the weight in our Dijkstras
        for e in self.e_type:
            self.e_time[e] = self.e_dist[e] * 60 / float(self.e_speed[e]) # in minutes

    def dijkstra(self, pair):
        path = [0, [pair[0]]]
        q = Queue.PriorityQueue()
        used = set()
        start = pair[0]
        end = pair[1]

        while start != end:
            if start not in used:
                used.add(start)
                for node in self.g[start]:
                    if node not in used:
                        new_list = list(path[1])
                        new_list.append(node)
                        #new_path = [path[0]+self.e_time[(start, node)]  + vincenty(start, node).miles/50 , new_list]
                        new_path = [path[0]+self.e_time[(start, node)], new_list]
                        q.put(tuple(new_path))
            if (q.empty()):
                return -1, []
            path = list(q.get())
            start = path[1][-1]

        return path[0], path[1]

    def iterate(self, numIter, numTest):
        test_pairs = {}
        if self.init_pairs == []:
            #Generate the random pairs of start-end locations
            for i in range(numTest):
                pair = (random.randint(0, self.num_nodes), random.randint(0, self.num_nodes))
                while pair[0] not in self.g:
                    # i-=1
                    # continue
                    pair = (random.randint(0, self.num_nodes), random.randint(0, self.num_nodes))
                # print "(%d, %d)," % (pair[0], pair[1])
                test_pairs[pair] = ()
        else:
            for p in self.init_pairs:
                test_pairs[p] = ()
        not_feasible = set()
        old_test_pairs = {}
        change_arr = []
        avg_dist_arr = []
        avg_dist_std_arr = []
        max_dist_arr = []
        min_dist_arr = []
        avg_time_arr = []
        avg_time_std_arr = []
        max_time_arr = []
        min_time_arr = []
        for i in range(numIter):
            print "Iteration ", i
            old_test_pairs = dict(test_pairs)
            #reset flow
            self.e_flow = {}
            for e in self.e_type:
                self.e_flow[e] = 0

            #go through the number of iterations
            for j, pair in enumerate(test_pairs):
                if pair in not_feasible:
                    continue
                #Associate our weights(time) with graph
                #Find shorteset path between all pairs
                time, path = self.dijkstra(pair)
                test_pairs[pair] = (time, path)
                if time == -1:
                    not_feasible.add(pair)
                    continue
                for k in range(len(path) - 1):
                    # self.e_flow[(path[k+1], path[k])]+=1

                    e = (path[k], path[k+1])
                    self.e_time[e] = self.e_dist[e] * 60 / float(self.e_speed[e]) # in minutes
                    if self.e_type[e] != "motorway" and self.e_type[e] != "trunk":
                        self.e_time[e] += 18.1/60 #MAGIC PART 2
                    self.e_time[e] *= (1 + 0.2 * pow(self.e_flow[e]*10 / (self.capacity[e] * 1400.0/60), 3) / (self.e_dist[e] * 5280)) #MAGIC
                    #print self.e_flow[e] * 500 / (self.capacity[e] * 1400.0/60 * self.e_dist[e] * 5280)
                    #print 0.2 * pow(self.e_flow[e] * 50 / (self.capacity[e] * 1400.0/60 * self.e_dist[e] * 5280), 2)
                    self.e_flow[(path[k], path[k+1])]+=1

            #for e in self.e_type:
            #    self.e_time[e] = self.e_dist[e] * 60 / float(self.e_speed[e]) # in minutes
            #    if self.e_type[e] != "motorway" and self.e_type[e] != "trunk":
            #        self.e_time[e] += 18.1/60 #MAGIC PART 2
            #    self.e_time[e] *= (1 + 0.2 * pow(self.e_flow[e]*2000 / (self.capacity[e] * 1400.0/60 * self.e_dist[e] * 5280), 2)) #MAGIC
            #   #print self.e_flow[e] * 500 / (self.capacity[e] * 1400.0/60 * self.e_dist[e] * 5280)
            #    print 1+ 0.2 * pow(self.e_flow[e] * 500 / (self.capacity[e] * 1400.0/60 * self.e_dist[e] * 5280), 2)

            #print self.e_flow
            print max(self.e_flow, key=self.e_flow.get)
            print max(self.e_flow.values())
            print max(self.e_time, key=self.e_time.get)
            print max(self.e_time.values())

            change = 0
            if i != 0:
                for j, pair in enumerate(old_test_pairs):
                    old_time, old_path = old_test_pairs[pair]
                    time, path = test_pairs[pair]
                    if path != old_path:
                        if j == 0:
                            print old_path
                            print path
                        change+=1
                print "Percentage change: ", change/float(len(old_test_pairs) - len(not_feasible))

                #Check how many paths changed to determine if terminate
                print change
                percent_change = change/float(len(old_test_pairs) - len(not_feasible))
                change_arr.append(percent_change)
                if percent_change < 0.05:
                    break

            f2 = open("candidate_results/final_path_base_map" + str(i) + ".txt", 'w')
            avg_dist = []
            avg_time = []
            for p in test_pairs:
                if p not in not_feasible:
                    avg_time.append(test_pairs[p][0])
                    path_len = 0
                    for lol in range(len(test_pairs[p][1]) - 1):
                        path_len+=self.e_dist[(test_pairs[p][1][lol],test_pairs[p][1][lol + 1])]
                    avg_dist.append(path_len)
                    for n in test_pairs[p][1]:
                        f2.write("%s " % str(n))
                    f2.write('\n')
            avg_dist_arr.append(sum(avg_dist)/float(numTest - len(not_feasible)))
            avg_dist_std_arr.append(numpy.std(avg_dist))
            max_dist_arr.append(max(avg_dist))
            min_dist_arr.append(min(avg_dist))
            avg_time_arr.append(sum(avg_time)/float(numTest - len(not_feasible)))
            avg_time_std_arr.append(numpy.std(avg_time))
            max_time_arr.append(max(avg_time))
            min_time_arr.append(min(avg_time))

        # END OF ITERATION #

        print "Percentage Change per it: ", change_arr
        print "Avg Distance per it: ", avg_dist_arr
        print "Avg Dist STD: ", avg_dist_std_arr
        print "Max Dist: ", max_dist_arr
        print "Min Dist: ", min_dist_arr
        print "Avg Time per it: ", avg_time_arr
        print "Avg Time STD: ", avg_time_std_arr
        print "Max Time: ", max_time_arr
        print "Min Time: ", min_time_arr
        f = open("candidate_results/edge_with_traffic_model.txt", 'w')
        for e in self.e_time:
            f.write( str(e[0]) +' '+ str(e[1]) + ' ' + str(self.e_time[e]) + '\n')


