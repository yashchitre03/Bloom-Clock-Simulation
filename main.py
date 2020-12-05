from math import factorial
from multiprocessing import Process, Value, Queue, Pool, cpu_count
import random
import time
import numpy as np
from queue import Empty
import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import os
from itertools import repeat


def positive_probability(b_y, b_z):
    """
    calculates the probability of a positive using the binomial distribution
    :param By: bloom clock By
    :param Bz: bloom clock bz
    :return: probability of positive
    """

    # calculate n choose k
    comb = lambda n, k: (factorial(n) // factorial(k) // factorial(n - k)) if n > k else 0

    mini = np.min(np.minimum(b_y, b_z))
    By = b_y - mini
    Bz = b_z - mini

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


def positive_probability_delta(By, Bz):
    """
    calculates the probability of a positive using the delta equation
    :param By: bloom clock By
    :param Bz: bloom clock Bz
    :return: probability of positive
    """

    return int((Bz >= By).all())


def metrics_helper(o1, o2):
    """
    helper function to calculate the actual and estimated metrics
    :param o1: event y object
    :param o2: event x object
    :return: computed metrics
    """
    # initialize
    tp, tn, fp, fn = 0, 0, 0, 0

    # extract the vector and bloom clocks for the y and z event (or x and x')
    _, Vy, By = o1
    _, Vz, Bz = o2

    # perform causality check
    vector_y_before_z = (Vy < Vz).all()
    bloom_y_before_z = (Bz >= By).all()

    # get the prediction scenarios
    if vector_y_before_z and bloom_y_before_z:
        tp = 1
    elif vector_y_before_z and not bloom_y_before_z:
        fn = 1
    elif not vector_y_before_z and bloom_y_before_z:
        fp = 1
    else:
        tn = 1

    # calculate pr_p and pr_delta-p for metrics without the vector clock
    pr_p = positive_probability(By, Bz)
    pr_delta_p = positive_probability_delta(By, Bz)
    numerator = (1 - pr_p) * pr_delta_p
    acc_denom = 1
    prec_denom = pr_delta_p
    fpr_denom = 1 - pr_p * pr_delta_p

    return np.array([tp, tn, fp, fn, numerator, acc_denom, prec_denom, fpr_denom])


def compute_metrics(events_data):
    """
    computes the accuracy, precision, and false positive rate of the events from the execution slice
    :param events_data: list of gsn, vector clocks, and bloom clocks for the execution slice
    :return: accuracy, precision, and false positive rate
    """

    pool_size = cpu_count() * 2
    with Pool(processes=pool_size) as pool:
        op = pool.starmap(metrics_helper, ((events_data[y], events_data[z]) for y in range(len(events_data)) for z in
                                           range(len(events_data)) if y != z))

    true_positive, true_negative, false_positive, false_negative, numerator, acc_denom, prec_denom, fpr_denom = np.sum(
        np.array(op), axis=0)

    # calculate the metrics
    accuracy = (true_positive + true_negative) / (true_positive + true_negative + false_positive + false_negative)
    precision = true_positive / (true_positive + false_positive)
    fpr = false_positive / (false_positive + true_negative)

    # calculate the metrics without vector clock
    accuracy_hat = 1 - (numerator / acc_denom)
    precision_hat = 1 - (numerator / prec_denom)
    fpr_hat = numerator / fpr_denom

    return map(round, (accuracy, precision, fpr, accuracy_hat, precision_hat, fpr_hat), repeat(4))


def plot(title, x_label, y_label, x_data, y_data, color, font_styles=dict(fontsize=20, fontweight='bold'), legend=True):
    """
    plots data for given values
    :param legend: whether to display the legend or not
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
    plt.xticks(fontsize=15)
    plt.yticks(fontsize=15)
    plt.scatter(x_data, y_data, c=color)
    if legend:
        red_dot = mlines.Line2D([], [], color='red', marker='o', linestyle='None',
                                markersize=10, label='Actual negative')
        green_dot = mlines.Line2D([], [], color='green', marker='o', linestyle='None',
                                  markersize=10, label='Actual positive')
        plt.legend(handles=[red_dot, green_dot], prop={'size': 15})
    plt.savefig(f'res{os.sep}{title}.png', bbox_inches='tight')
    plt.show()


def tabulate(title, cols, data):
    """
    creates a table for the given data
    :param title: title of the table
    :param cols: column labels of the table
    :param data: data to fill the table
    :return: None
    """

    fig, ax = plt.subplots()
    table = ax.table(cellText=data, colLabels=cols,
                     cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(55)
    table.scale(15, 10)
    ax.axis('off')
    plt.savefig(f'res{os.sep}{title}.png', bbox_inches='tight')
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
            time.sleep(random.random())

    # give all processes some time to warm-up
    time.sleep(1 - (process_id / n))

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


if __name__ == '__main__':
    """
    driver code. change the parameters as suitable for each simulation and run
    """
    # start of program
    print('Main process started')

    # initialize shared memory variables
    global_seq_num = Value('i')

    # initializing list for results table
    table_w_VC, table_wo_VC = [], []

    # probability of an internal event
    internal_prob = 0

    # number of processes
    n = 100

    # the important GSN values to capture for final results
    lower_limit = (10 * n)
    upper_limit = n ** 2 + (10 * n) + 1
    capture_values = {val for val in range(lower_limit + 1, upper_limit, 10)}
    capture_values.add(lower_limit)

    for m in map(int, (0.1 * n, 0.2 * n, 0.3 * n)):
        for k in (2, 3, 4):

            s = time.time()
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
                process_obj.terminate()

            # calculate the probabilities for each data point
            first = min(res)
            _, Vy, By = first
            res.remove(first)
            gsn_list, pr_p, pr_fp, pr_fp_delta, actual_pn_colors = [], [], [], [], []

            even_err_count = 0
            for gsn, Vz, Bz in res:

                if np.sum(Bz) % 2 == 1:
                    even_err_count += 1

                gsn_list.append(gsn)

                pos = positive_probability(By, Bz)
                pr_p.append(pos)

                false_pos = (1 - pos) * pos
                pr_fp.append(false_pos)

                false_pos_delta = (1 - pos) * positive_probability_delta(By, Bz)
                pr_fp_delta.append(false_pos_delta)

                actual_pn_colors.append('green' if (Vy < Vz).all() else 'red')

            # plot the data
            plot(title=f'Pr_p: n = {n}; m = {m}; k = {k}',
                 x_label='GSN (Global Sequence Number)', y_label='Pr_p (Probability of positive)',
                 x_data=gsn_list, y_data=pr_p, color='b', legend=False)

            plot(title=f'Pr_fp ((1-pr_p)pr_p): n = {n}; m = {m}; k = {k}',
                 x_label='GSN (Global Sequence Number)', y_label='Pr_fp (Probability of false positive)',
                 x_data=gsn_list, y_data=pr_fp, color=actual_pn_colors)

            plot(title=f'Pr_fp ((1-pr_p)pr_{{delta(p)}}): n = {n}; m = {m}; k = {k}',
                 x_label='GSN (Global Sequence Number)', y_label='Pr_fp (delta) (Probability of false positive)',
                 x_data=gsn_list, y_data=pr_fp_delta, color=actual_pn_colors)

            acc, prec, fpr, acc_hat, prec_hat, fpr_hat = compute_metrics(res)
            table_w_VC.append((n, m, k, acc, prec, fpr))
            table_wo_VC.append((n, m, k, acc_hat, prec_hat, fpr_hat))

            e = time.time()
            print(f'Simulation\'s total runtime: {e - s} with even error: {even_err_count}')

    # tabulate the data
    col_labels = ['Number of processes (n)',
                  'Bloom clock size (m)',
                  'Number of hash functions (k)',
                  'Accuracy',
                  'Precision',
                  'False positive rate (fpr)']
    tabulate(title='Table for equation 6', cols=col_labels, data=table_w_VC)
    tabulate(title='Table for equations 10, 11 ,12', cols=col_labels, data=table_wo_VC)

    # end of program
    print(f'Main process ended')
