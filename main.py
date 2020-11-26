from multiprocessing import Process, Pipe, Value
import random
import time
import numpy as np


def process_i(id, pipes, GSN, n, m, k, prob):

    def update_clock():
        # update vector clock
        vector_clock[id] += 1

        # update bloom clock
        for seed in range(k):
            hash_val = hash((id, seed))
            index = hash_val % m
            bloom_clock[index] += 1

    # initialize the clocks
    vector_clock = np.zeros(n)
    bloom_clock = np.zeros(m)

    while GSN.value < 100:

        # SEND EVENT
        with GSN.get_lock():
            GSN.value += 1
        pipe = random.choice(pipes)
        update_clock()
        pipe.send((vector_clock, bloom_clock))

        # INTERNAL EVENT
        uniform_dist_val = random.random()
        if uniform_dist_val < prob:
            with GSN.get_lock():
                GSN.value += 1
            update_clock()
            time.sleep(uniform_dist_val)

        # RECEIVE EVENT
        for pipe in pipes:
            while GSN.value < 100 and pipe.poll():
                try:
                    other_vector_clock, other_bloom_clock = pipe.recv()
                except EOFError:
                    pipes.remove(pipe)
                else:
                    with GSN.get_lock():
                        GSN.value += 1
                    np.maximum(vector_clock, other_vector_clock, vector_clock)
                    np.maximum(bloom_clock, other_bloom_clock, bloom_clock)
                    update_clock()

    # final state of the clocks
    print(f'Process {id}:\nVector Clock -> {vector_clock}\nBloom Clock -> {bloom_clock}\n')


if __name__ == '__main__':
    # start of program
    print('Main process started')

    # define parameters n, m, and k
    n = 20
    m = int(0.1 * n)
    k = 2

    # probability of an internal event
    prob = 1

    # initialize shared memory variables
    GSN = Value('i')

    # initialize the pipe objects for message-passing
    pipes = [[] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            first_end, second_end = Pipe()
            pipes[i].append(first_end)
            pipes[j].append(second_end)

    # create process objects with the required arguments
    processes = []
    for i in range(n):
        process = Process(target=process_i, kwargs={'id': i,
                                                    'pipes': pipes[i],
                                                    'GSN': GSN,
                                                    'n': n,
                                                    'm': m,
                                                    'k': k,
                                                    'prob': prob})
        processes.append(process)

    # run the processes
    for process in processes:
        process.start()

    # wait for the children processes to finish
    for process in processes:
        process.join()

    # plotting logic starts here
    # TODO: plot the results

    # end of program
    print(f'Main process ended (GSN value = {GSN.value})')