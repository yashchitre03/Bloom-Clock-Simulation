from multiprocessing import Process, Pipe, Value
import random
import time


def process_i(id, pipes, GSN):
    logical_time = 0

    while GSN.value < 1000:

        # SEND EVENT
        pipe = random.choice(pipes)
        with GSN.get_lock():
            GSN.value += 1

        logical_time += 1
        print(f'Time: {logical_time};    Type: SEN;    MyID: {id};    OtherID: ?')
        pipe.send((id, logical_time))
        time.sleep(random.randint(1, 10))

        # RECEIVE EVENT
        for pipe in pipes:
            while pipe.poll():
                try:
                    msg, other_time = pipe.recv()
                except EOFError:
                    pipes.remove(pipe)
                else:
                    with GSN.get_lock():
                        GSN.value += 1
                    logical_time = max(logical_time, other_time) + 1
                    print(f'Time: {logical_time};    Type: REC;    MyID: {id};    OtherID: {msg}')


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

    # with Pool(processes=n) as pool:
    #     pool.starmap(func=process_i, iterable=[(i, pipes[i], GSN) for i in range(n)])

    processes = []
    for i in range(n):
        process = Process(target=process_i, args=(i, pipes[i], GSN))
        processes.append(process)

    for process in processes:
        process.start()

    for process in processes:
        process.join()

    print('ENDDD', GSN.value)
    print('Main process ended')
