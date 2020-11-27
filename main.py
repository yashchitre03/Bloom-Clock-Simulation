import math
from multiprocessing import Process, Pipe, Value, Queue
import random
import time
import numpy as np
from queue import Empty
import matplotlib.pyplot as plt


def positive_probability(m, By, Bz):
    """
    calculates the probability of a positive
    :param m: the size of bloom clock
    :param By: bloom clock By
    :param Bz: bloom clock bz
    :return: probability of positive
    """

    # calculate n choose k
    comb = lambda n, k: math.factorial(n) // math.factorial(k) // math.factorial(n - k)

    n = np.sum(Bz)
    p = 1 / m
    probability = 1
    for i in range(m):
        sum_b = 0
        for l in range(By[i]):
            # bernoulli trial formula
            sum_b += comb(n, l) * (p ** l) * ((1 - p) ** (n - l))
        probability *= (1 - sum_b)

    return probability


def process(process_id, send_conns, receive_conn, GSN, parent_queue):
    def update_clock():
        # update vector clock
        vector_clock[process_id] += 1

        # update bloom clock
        for seed in range(k):
            hash_val = hash((process_id, event_count, seed))
            index = hash_val % m
            bloom_clock[index] += 1

    # number of events executed at the current process
    event_count = 0

    # initialize the clocks
    vector_clock = np.zeros(n, dtype=np.uint32)
    bloom_clock = np.zeros(m, dtype=np.uint32)

    while GSN.value < upper_limit:

        # SEND EVENT
        with GSN.get_lock():
            GSN.value += 1
            cur_gsn = GSN.value
        event_count += 1
        update_clock()
        pj_queue = random.choice(send_conns)
        pj_queue.put((vector_clock, bloom_clock))

        # check if the clock should be captured
        if cur_gsn in capture_values:
            parent_queue.put((cur_gsn, bloom_clock))

        # INTERNAL EVENT
        uniform_dist_val = random.random()
        if uniform_dist_val < internal_prob:
            with GSN.get_lock():
                GSN.value += 1
                cur_gsn = GSN.value
            event_count += 1
            update_clock()
            time.sleep(uniform_dist_val)

            # check if the clock should be captured
            if cur_gsn in capture_values:
                parent_queue.put((cur_gsn, bloom_clock))

        # RECEIVE EVENT
        try:
            other_vector_clock, other_bloom_clock = receive_conn.get(block=False)
        except Empty:
            pass
        else:
            with GSN.get_lock():
                GSN.value += 1
                cur_gsn = GSN.value
            event_count += 1
            np.maximum(vector_clock, other_vector_clock, vector_clock)
            np.maximum(bloom_clock, other_bloom_clock, bloom_clock)
            update_clock()

            # check if the clock should be captured
            if cur_gsn in capture_values:
                parent_queue.put((cur_gsn, bloom_clock))

        time.sleep(random.random())

    # final state of the clocks
    # print(f'Process {process_id}:\nVector Clock -> {vector_clock}\nBloom Clock -> {bloom_clock}\n')


if __name__ == '__main__':
    # start of program
    print('Main process started')

    # define parameters n, m, and k
    n = 20
    m = int(0.1 * n)
    k = 2

    # probability of an internal event
    internal_prob = 0

    # initialize shared memory variables
    global_seq_num = Value('i')

    # initialize the queue objects for message passing communication
    queue_objs = []
    for _ in range(n):
        queue_objs.append(Queue())

    # the important GSN values to capture for final results
    lower_limit = (10 * n)
    upper_limit = n ** 2 + (10 * n)
    capture_values = {val for val in range(lower_limit + 1, upper_limit, 10)}
    capture_values.add(lower_limit)

    # main queue to get the desired data from the simulation
    main_queue = Queue()

    # create process objects with the required arguments
    processes = []
    for i in range(n):
        process_queues = queue_objs[:]
        self_queue = process_queues.pop(i)
        other_queues = process_queues
        process_obj = Process(target=process, kwargs=dict(process_id=i, receive_conn=self_queue,
                                                          send_conns=other_queues, GSN=global_seq_num,
                                                          parent_queue=main_queue))
        processes.append(process_obj)

    # run the processes
    for process_obj in processes:
        process_obj.start()

    # wait for the children processes to finish
    for process_obj in processes:
        process_obj.join()

    # extract data from the main queue
    res = []
    while not main_queue.empty():
        res.append(main_queue.get(block=False))
    res.sort()

    # calculate the probabilities for each data point
    By = res[0][1]
    plot_data = []
    for gsn, Bz in res[1: ]:
        pr_p = positive_probability(m, By, Bz)
        plot_data.append((gsn, pr_p))

    # plot the data
    plt.plot(*(zip(*plot_data)))

    # end of program
    print(f'Main process ended (GSN value = {global_seq_num.value})')
