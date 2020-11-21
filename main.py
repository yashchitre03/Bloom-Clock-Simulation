from multiprocessing import Process, Pipe, Value
import random
import time
import numpy as np


def process_i(id, pipes, GSN, n):
    vector_clock = np.zeros(n, dtype=np.int16)

    while GSN.value < 1000000:

        # SEND EVENT
        pipe = random.choice(pipes)
        with GSN.get_lock():
            GSN.value += 1

        vector_clock[id] += 1
        #print(f'Time: {vector_clock};    Type: SEN;    MyID: {id};    OtherID: ?')
        pipe.send((id, vector_clock))

        time.sleep(random.random())

        # RECEIVE EVENT
        for pipe in pipes:
            while pipe.poll():
                try:
                    msg, other_clock = pipe.recv()
                except EOFError:
                    pipes.remove(pipe)
                else:
                    with GSN.get_lock():
                        GSN.value += 1

                    np.maximum(vector_clock, other_clock, vector_clock)
                    vector_clock[id] += 1
                    #print(f'Time: {vector_clock};    Type: REC;    MyID: {id};    OtherID: {msg}')
    print(f'Process {id}: {vector_clock}')


if __name__ == '__main__':
    print('Main process started')
    n = 100
    pipes = [[] for _ in range(n)]
    GSN = Value('i')

    for i in range(n):
        for j in range(i + 1, n):
            first_end, second_end = Pipe()
            pipes[i].append(first_end)
            pipes[j].append(second_end)

    processes = []
    for i in range(n):
        process = Process(target=process_i, args=(i, pipes[i], GSN, n))
        processes.append(process)

    for process in processes:
        process.start()

    for process in processes:
        process.join()

    print('END', GSN.value)
    print('Main process ended')
