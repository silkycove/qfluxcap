# qfluxcap.py Copyright (c) 2021 Masami Yamakawa
# SPDX-License-Identifier: MIT
#

from time import process_time
from time import sleep
from qiskit import IBMQ, QuantumCircuit, execute, BasicAer
from qiskit.providers import JobStatus
from qiskit.providers.ibmq import least_busy
import argparse
from multiprocessing import Process
from multiprocessing import Queue
import RPi.GPIO as GPIO

ap = argparse.ArgumentParser()
ap.add_argument('-q', '--qasm', default='ghz.qasm',
                help='path to qasm file')

ap.add_argument('-b', '--backend', default='qasm_simulator',
                help='backend name')

ap.add_argument('-s', '--shots', default=200, type=int,
                help='number of shots')

ap.add_argument('-r', '--run_timeout', default=300, type=int,
                help='job running timeout')

ap.add_argument('-f', '--flash', default=5, type=int,
                help='flush delay millis')

args = ap.parse_args()

qasm_file_name = args.qasm
backend_name = args.backend
number_of_shots = args.shots
run_timeout = args.run_timeout
flash_delay = args.flash


def led_proc(in_queue):

    LED_PINS = [22, 23, 24, 25]

    GPIO.setmode(GPIO.BCM)

    for pin in LED_PINS:
        GPIO.setup(pin, GPIO.OUT)

    patterns = ['1111']
    delay_ms = 500
    delay_ms_patterns = 0

    while True:

        if not in_queue.empty():
            patterns, delay_ms, delay_ms_patterns = in_queue.get()

        for pattern in patterns:

            pattern = pattern.replace(' ', '')

            for (i, led_state) in enumerate(list(pattern)):
                GPIO.output(LED_PINS[i], int(led_state))

                if delay_ms > 0:
                    sleep(delay_ms/1000)

                GPIO.output(LED_PINS[i], 0)

            if delay_ms_patterns > 0:
                sleep(delay_ms_patterns/1000)


def start_ibmq():

    if backend_name == 'qasm_simulator':
        q = BasicAer.get_backend('qasm_simulator')

    else:
        provider = IBMQ.load_account()

        if backend_name == 'least_busy':
            print('Finding least busy 5 qubits backend...')
            q5_devices = provider.backends(
                            filters=lambda x: x.configuration().n_qubits == 5
                            and not x.configuration().simulator)

            q = least_busy(q5_devices)
            backend = q.name()

            print('Least Busy Backend:', backend)
            status = q.status()
            jobs_in_queue = status.pending_jobs
            print('Jobs in queue:', jobs_in_queue)
        else:
            q = provider.get_backend(backend_name)
    return q


def main():

    try:

        with open(qasm_file_name) as f:
            qasm = f.read()

        print("OpenQASM code:\n", qasm)

        qc = QuantumCircuit.from_qasm_str(qasm)
        print(qc)

        q = start_ibmq()

        backend_status = q.status()

        print('Backend Status:', backend_status.status_msg)

        if (backend_name == 'qasm_simulator'
                or q.status().status_msg == 'active'):

            job = execute(qc, q, shots=number_of_shots, memory=True)
            job_start_time = process_time()

            while True:
                job_status = job.status()
                print('Status:', job_status)

                if job_status == JobStatus.RUNNING:
                    in_queue.put((['1111'], 10, 0))
                    if process_time() - job_start_time > run_timeout:
                        print('[IBMQ] run time too long!')
                        break

                elif job_status == JobStatus.QUEUED:
                    in_queue.put((['1111'], 200, 0))

                elif job_status == JobStatus.ERROR:
                    print('[IBMQ] Job error!', job_status)
                    break

                elif job_status == JobStatus.DONE:
                    break

                sleep(5)

            if job_status == JobStatus.DONE:

                result = job.result()     # get the result
                counts = result.get_counts(qc)
                counts_key_list = list(counts.keys())
                readouts = result.get_memory()
                print('readouts', readouts)
                in_queue.put((readouts, flash_delay, 0))

                for old_key in counts_key_list:
                    new_key = old_key.replace(' ', '')
                    counts[new_key] = counts.pop(old_key)

                print(counts)

                maxpattern = max(counts, key=counts.get)
                maxvalue = counts[maxpattern]
                print("Maximum value:", maxvalue,
                      "Maximum pattern:", maxpattern)

                sleep(180)

    except Exception as e:
        print('ERROR!', e)

    in_queue.put((['0000'], 0, 0))
    sleep(5)


if __name__ == "__main__":

    in_queue = Queue(maxsize=1)

    p = Process(target=led_proc, args=(in_queue,))
    p.daemon = True
    p.start()

    main()
