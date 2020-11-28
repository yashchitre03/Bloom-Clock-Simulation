import math
from multiprocessing import Process, Value, Queue
import random
import time
import numpy as np
from queue import Empty
import matplotlib.pyplot as plt


def positive_probability(By, Bz):
    """
    calculates the probability of a positive using the binomial distribution
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
            # binomial distribution formula
            sum_b += comb(n, l) * (p ** l) * ((1 - p) ** (n - l))
        probability *= (1 - sum_b)

    return probability


def plot(title, x_label, y_label, x_data, y_data, color, font_styles=dict(fontsize=20, fontweight='bold')):
    """
    plots data for given values
    :param title: heading of the plot
    :param x_label: label of X-axis
    :param y_label: label of Y-axis
    :param x_data: data points for X-axis
    :param y_data: data points for Y-axis
    :param color: color of the plot points
    :param font_styles: different styling options
    :return: None
    """
    fig = plt.figure(figsize=(20, 10))
    fig.set_facecolor('w')
    plt.title(label=title, fontdict=font_styles)
    plt.xlabel(x_label, fontdict=font_styles)
    plt.ylabel(y_label, fontdict=font_styles)
    plt.scatter(x_data, y_data, c=color)
    plt.show()


def process(process_id, send_conns, receive_conn, GSN, parent_queue):
    """
    code for each process Pi to run asynchronously
    :param process_id: unique identifier for each process
    :param send_conns: queues of other processes
    :param receive_conn: queue of itself
    :param GSN: Global Sequence Number
    :param parent_queue: queue to send the simulation data for later processing
    :return: --
    """

    def update_clock():
        """
        updates the vector and bloom clocks of the process
        :return:
        """
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
            parent_queue.put((cur_gsn, vector_clock, bloom_clock))

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
                parent_queue.put((cur_gsn, vector_clock, bloom_clock))

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
                parent_queue.put((cur_gsn, vector_clock, bloom_clock))

        time.sleep(random.random())

    # final state of the clocks
    # print(f'Process {process_id}')


if __name__ == '__main__':
    # start of program
    print('Main process started')

    # probability of an internal event
    internal_prob = 0

    # initialize shared memory variables
    global_seq_num = Value('i')

    for n in (20, ):
        # the important GSN values to capture for final results
        lower_limit = (10 * n)
        upper_limit = n ** 2 + (10 * n) + 1
        capture_values = {val for val in range(lower_limit + 1, upper_limit, 10)}
        capture_values.add(lower_limit)

        for m in (int(0.1 * n), int(0.2 * n), int(0.3 * n)):
            for k in (2, 3, 4):
                # reset GSN
                global_seq_num.value = 0

                # initialize the queue objects for message passing communication
                queue_objs = []
                for _ in range(n):
                    queue_objs.append(Queue())

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

                # extract data from the main queue
                res = []
                for _ in range(len(capture_values)):
                    res.append(main_queue.get())

                # wait for the children processes to finish
                for process_obj in processes:
                    process_obj.join()

                # calculate the probabilities for each data point
                res.sort()
                _, Vy, By = res[0]
                gsn_list, pr_p, pr_fp, pr_fp_delta, actual_pn_colors = [], [], [], [], []
                for gsn, Vz, Bz in res[1:]:
                    gsn_list.append(gsn)

                    pos = positive_probability(By, Bz)
                    pr_p.append(pos)

                    false_pos = (1 - pos) * pos
                    pr_fp.append(false_pos)

                    false_pos_delta = (1 - pos) * int((Bz >= By).all())
                    pr_fp_delta.append(false_pos_delta)

                    actual_pn_colors.append('green' if int((Vy < Vz).all()) else 'red')

                # plot the data
                plot(title=f'Pr_p: n = {n}; m = {m}; k = {k}',
                     x_label='GSN (Global Sequence Number)', y_label='Pr_p (Probability of positive)',
                     x_data=gsn_list, y_data=pr_p, color='blue')

                plot(title=f'Pr_fp: n = {n}; m = {m}; k = {k}',
                     x_label='GSN (Global Sequence Number)', y_label='Pr_fp (Probability of false positive)',
                     x_data=gsn_list, y_data=pr_fp, color=actual_pn_colors)

                plot(title=f'Pr_fp (delta equation): n = {n}; m = {m}; k = {k}',
                     x_label='GSN (Global Sequence Number)', y_label='Pr_fp for delta (Probability of false positive)',
                     x_data=gsn_list, y_data=pr_fp_delta, color=actual_pn_colors)

    # end of program
    print(f'Main process ended (GSN value = {global_seq_num.value})')
