"""
TODO: Description of what this file does.

How to run:
1. A. Have 2 terminals open
    a. ~/ardupilot_ws/src/ardupilot# ./Tools/autotest/sim_vehicle.py -v ArduCopter --vehicle=ArduCopter --frame=hexa
    B. mavproxy.py --master 127.0.0.1:14551 --out=udp:127.0.0.1:14552 --out=udp:127.0.0.1:14553
1. B. (OR) Connect real vehicle on USB or RT
2. Open QGC/Ground control - it will auto connect to 127.0.0.1:14550 or 127.0.0.1:14551
3. Run this file
"""

import os
import sys
import time
from dronekit import VehicleMode
from pymavlink import mavutil

from simple_pid import PID

cur_path=os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, cur_path+"/..")

from src.droneforce import DroneForce
from src.autopilot import DFAutopilot
from src.utility.logger import *
from src.dynamics.inertia import DFInertia
from src.dynamics.mass import DFMass
from src.dynamics.frame import DFFrame, Frames
from src.dynamics.motors import DFMotor
from src.controller.p_controller import P_Controller

from src.utility.map_range import map_range, torque_to_PWM

import numpy as np

logging.debug('Beginning of code...')

timestep = 0.01

if __name__ == '__main__':
    mass = DFMass(1000)
    inertia = DFInertia(1,1,1)

    frame = DFFrame(frame_type=Frames.Hexa_X)

    with DroneForce(mass=mass, inertia=inertia, frame=frame) as drone:
        logging.debug("Ready: %s", drone)

        ea_matrix = drone.frame.EA
        ca_matrix = drone.frame.CA
        logging.info(f'Frame type: \n{len(drone.frame.frame_type.value)}')

        logging.info(f'Effectiveness: \n{ea_matrix}')
        logging.info(f'Control Allocation: \n{ca_matrix}')

        connection_string = '127.0.0.1:14553'

        with DFAutopilot(connection_string=connection_string) as commander:
            logging.debug("Ready: %s", commander)

            # Reset all motor configs
            commander.set_motor_mode(1, 1)
            commander.set_motor_mode(2, 1)
            commander.set_motor_mode(3, 1)
            commander.set_motor_mode(4, 1)
            commander.set_motor_mode(5, 1)
            commander.set_motor_mode(6, 1)

            logging.debug("Basic pre-arm checks")
            # Don't try to arm until autopilot is ready
            while not commander.master.is_armable:
                logging.debug(" Waiting for vehicle to initialise...")
                time.sleep(1)

            print("Arming motors")
            # Copter should arm in GUIDED mode
            commander.master.mode = VehicleMode("GUIDED")
            commander.master.armed = True

            # Confirm vehicle armed before attempting to take off
            while not commander.master.armed:
                print(" Waiting for arming...")
                time.sleep(1)

            # Add P Controller takeoff
            print("Taking off!")

            with P_Controller(Kp=0.085) as controller:
                # get rpy from dronekit

                z = commander.master.location.global_relative_frame.alt
                des_z = 10

                Tp_des = 0
                Tq_des = 0
                Tr_des = 0
                T_des = 0
                Torq = [Tp_des, Tq_des, Tr_des, T_des]

                # Start point
                # pid = PID(0.25, 0.5, 0.5)
                
                # 8 to 13 range
                # pid = PID(0.75, 0.01, 0.1)
                
                # 8.7 to 12.3 range
                # pid = PID(0.75, 0.01, 0.5)
                
                # crash to 13.7 range
                # pid = PID(0.75, 0.01, 0.75)
                
                # 8.8 to 13.7 range
                # pid = PID(0.75, 0.01, 0.55)
                
                # 2.8 to 13.8 range
                # pid = PID(0.75, 0.05, 0.50)
                
                # 8.5 to 12.8 range
                # pid = PID(0.75, 0.01, 0.55)
                
                # 7.25 to 11.8 range
                # pid = PID(0.95, 0.01, 0.55)
                
                # 8.5 to 11.9 range
                # pid = PID(0.7, 0.01, 0.55)
                
                # crash to 11.5 range
                # pid = PID(0.65, 0.01, 0.55)
                
                # 8 to 14 range
                # pid = PID(0.75, 0.01, 0.05)

                # Works OK
                # pid = PID(0.2, 0.01, 0.0)
                
                # Works OK
                pid = PID(0.175, 0.00475, 0.001)

                # Testing this
                # Turns out to be cruicial
                # pid.proportional_on_measurement = True
                
                
                pid.sample_time = timestep

                # Above PID tests
                # pid.output_limits = (1.5, 2.5) 
                pid.output_limits = (0.75, 10.0) 
                # pid.output_limits = (0, 5) 

                while True:
                    pid.setpoint = des_z
                    z = commander.master.location.global_relative_frame.alt
                    Torq = [Tp_des, Tq_des, Tr_des, T_des]
                    u_input = np.matmul(drone.frame.CA_inv, Torq)
                    print(f"z: {z}")
                    print(f"des_z: {des_z}")
                    print(f"T_des: {T_des}")
                    print(f"Torq: {Torq}")


                    # Compute new output from the PID according to the systems current value
                    T_des = pid(z)
                    print(f"PID: {T_des}")

                    # Convert motor torque (input u) to PWM
                    PWM_out_values = []
                    i = 0
                    for input in u_input:
                        PWM = torque_to_PWM(input, (frame.frame_type.value[i]))
                        i = i + 1
                        PWM_out_values.append(PWM)

                    print(f"PWM outputs: {PWM_out_values}\n")
                    i=1
                    for PWM in PWM_out_values:
                        commander.set_servo(i, PWM)
                        i = i+1

                    time.sleep(timestep)
