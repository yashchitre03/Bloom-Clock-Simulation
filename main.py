from multiprocessing import Process, Pipe, Value, Queue
import random
import time
import numpy as np
from queue import Empty


def process(process_id, send_conns, receive_conn, GSN, n, m, k, prob):
    def update_clock():
        # update vector clock
        vector_clock[process_id] += 1

        # update bloom clock
        for seed in range(k):
            hash_val = hash((id, seed))
            index = hash_val % m
            bloom_clock[index] += 1

    # initialize the clocks
    vector_clock = np.zeros(n, dtype=np.uint32)
    bloom_clock = np.zeros(m, dtype=np.uint32)

    while GSN.value < 100:

        # SEND EVENT
        with GSN.get_lock():
            GSN.value += 1
        update_clock()
        pj_queue = random.choice(send_conns)
        pj_queue.put((vector_clock, bloom_clock))

        # INTERNAL EVENT
        uniform_dist_val = random.random()
        if uniform_dist_val < prob:
            with GSN.get_lock():
                GSN.value += 1
            update_clock()
            time.sleep(uniform_dist_val)

        # RECEIVE EVENT
        try:
            other_vector_clock, other_bloom_clock = receive_conn.get(block=False)
        except Empty:
            pass
        else:
            with GSN.get_lock():
                GSN.value += 1
            np.maximum(vector_clock, other_vector_clock, vector_clock)
            np.maximum(bloom_clock, other_bloom_clock, bloom_clock)
            update_clock()

    # final state of the clocks
    print(f'Process {process_id}:\nVector Clock -> {vector_clock}\nBloom Clock -> {bloom_clock}\n')


if __name__ == '__main__':
    # start of program
    print('Main process started')

    # define parameters n, m, and k
    num_processes = 20
    bloom_size = int(0.1 * num_processes)
    num_hash = 2

    # probability of an internal event
    internal_prob = 0

    # initialize shared memory variables
    global_seq_num = Value('i')

    # initialize the queue objects for message passing communication
    queue_objs = []
    for _ in range(num_processes):
        queue_objs.append(Queue())

    # create process objects with the required arguments
    processes = []
    for i in range(num_processes):
        process_queues = queue_objs[:]
        self_queue = process_queues.pop(i)
        other_queues = process_queues
        process_obj = Process(target=process, kwargs=dict(process_id=i, receive_conn=self_queue,
                                                          send_conns=other_queues, GSN=global_seq_num,
                                                          n=num_processes, m=bloom_size, k=num_hash,
                                                          prob=internal_prob))
        processes.append(process_obj)

    # run the processes
    for process_obj in processes:
        process_obj.start()

    # wait for the children processes to finish
    for process_obj in processes:
        process_obj.join()

    # plotting logic starts here
    # TODO: plot the results

    # end of program
    print(f'Main process ended (GSN value = {global_seq_num.value})')
