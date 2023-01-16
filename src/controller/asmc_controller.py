#!/usr/bin/env python
import sys
# ROS python API
import rospy

import tf.transformations as transformations

# 3D point & Stamped Pose msgs
from trajectory_msgs.msg import MultiDOFJointTrajectory as Mdjt
# from msg_check.msg import PlotDataMsg


import numpy as np
from tf.transformations import *
#import RPi.GPIO as GPIO
import time

import logging


class ASMC_Controller:
    """ ASMC Controller manager. """
    # initialization method
    def __init__(self):
        # Instantiate a setpoints message
        self.sp = []
        # set the flag to use position setpoints and yaw angle
       
        # Step size for position update
        self.STEP_SIZE = 2.0
        # Fence. We will assume a square fence for now
        self.FENCE_LIMIT = 5.0

        # A Message for the current local position of the drone
        # Parameters for PX4
        # NAV_RCL_ACT 0
        # COM_RCL_EXCEPT 4
        # NAV_DLL_ACT 0

        # initial values for setpoints
        self.cur_pose = []

        self.cur_pose.pose.position.x = 0
        self.cur_pose.pose.position.y = 0
        self.cur_pose.pose.position.z = 0

        self.cur_pose.pose.orientation.w = 0
        self.cur_pose.pose.orientation.x = 0
        self.cur_pose.pose.orientation.y = 0
        self.cur_pose.pose.orientation.z = 0

        self.cur_vel = []
        self.sp.pose.position.x = 0.0
        self.sp.pose.position.y = 0.0
        self.ALT_SP = 1.0
        self.sp.pose.position.z = self.ALT_SP
        self.local_pos = [0.0, 0.0, self.ALT_SP]
        self.local_quat = np.array([0.0, 0.0, 0.0, 1.0])
        self.desVel = np.zeros(3)
        self.errInt = np.zeros(3)
        self.att_cmd = []
        self.thrust_cmd = []

        # Control parameters
        self.Kp0 = np.array([1.0, 1.0, 1.0])
        self.Kp1 = np.array([2.0, 2.0, 1.0])

        self.Lam = np.array([2.0, 2.0, 3.0])
        self.Phi = np.array([1.5, 1.5, 1.0])
        self.M = 0.1

        self.alpha_0 = np.array([1,1,1])
        self.alpha_1 = np.array([3,3,3])
        self.alpha_m = 0.01
        self.v = 0.1

        self.norm_thrust_const = 0.06
        self.max_th = 16.0
        self.max_throttle = 0.96
        
        self.gravity = np.array([0, 0, 9.8])
        self.pre_time = time.time()    
        # self.data_out = PlotDataMsg()

        # Publishers
        # Add att and thrust pub
        # self.att_pub = rospy.Publisher('mavros/setpoint_attitude/attitude', PoseStamped, queue_size=10)
        # self.thrust_pub = rospy.Publisher('mavros/setpoint_attitude/thrust', Thrust, queue_size=10)
        # self.data_pub = rospy.Publisher('/data_out', PlotDataMsg, queue_size=10)
        self.armed = False
        self.pin_1 = 16
        self.pin_2 = 18

    def __enter__(self):
        return self

    def __exit__(self, *args):
        x = 0
        # Kill variables here

    def multiDoFCb(self, msg):
        pt = msg.points[0]
        self.sp.pose.position.x = pt.transforms[0].translation.x
        self.sp.pose.position.y = pt.transforms[0].translation.y
        self.sp.pose.position.z = pt.transforms[0].translation.z
        # self.data_out.sq = self.sp.pose.position
        self.desVel = np.array([pt.velocities[0].linear.x, pt.velocities[0].linear.y, pt.velocities[0].linear.z])
        # self.desVel = np.array([pt.accelerations[0].linear.x, pt.accelerations[0].linear.y, pt.accelerations[0].linear.z])
        # self.array2Vector3(sp.pose.position, self.data_out.acceleration)

    ## local position callback
    def posCb(self, msg):
        self.local_pos.x = msg.pose.position.x
        self.local_pos.y = msg.pose.position.y
        self.local_pos.z = msg.pose.position.z
        self.local_quat[0] = msg.pose.orientation.x
        self.local_quat[1] = msg.pose.orientation.y
        self.local_quat[2] = msg.pose.orientation.z
        self.local_quat[3] = msg.pose.orientation.w

    ## Update setpoint message
    def updateSp(self):
        self.sp.pose.position.x = self.local_pos.x
        self.sp.pose.position.y = self.local_pos.y
        # self.sp.position.z = self.local_pos.z

    def odomCb(self, msg):
        self.cur_pose.pose.position.x = msg.pose.pose.position.x
        self.cur_pose.pose.position.y = msg.pose.pose.position.y
        self.cur_pose.pose.position.z = msg.pose.pose.position.z

        self.cur_pose.pose.orientation.w = msg.pose.pose.orientation.w
        self.cur_pose.pose.orientation.x = msg.pose.pose.orientation.x
        self.cur_pose.pose.orientation.y = msg.pose.pose.orientation.y
        self.cur_pose.pose.orientation.z = msg.pose.pose.orientation.z

        self.cur_vel.twist.linear.x = msg.twist.twist.linear.x
        self.cur_vel.twist.linear.y = msg.twist.twist.linear.y
        self.cur_vel.twist.linear.z = msg.twist.twist.linear.z

        self.cur_vel.twist.angular.x = msg.twist.twist.angular.x
        self.cur_vel.twist.angular.y = msg.twist.twist.angular.y
        self.cur_vel.twist.angular.z = msg.twist.twist.angular.z

    def newPoseCB(self, msg):
        if(self.sp.pose.position != msg.pose.position):
            print("New pose received")
        self.sp.pose.position.x = msg.pose.position.x
        self.sp.pose.position.y = msg.pose.position.y
        self.sp.pose.position.z = msg.pose.position.z
   
        self.sp.pose.orientation.x = msg.pose.orientation.x
        self.sp.pose.orientation.y = msg.pose.orientation.y
        self.sp.pose.orientation.z = msg.pose.orientation.z
        self.sp.pose.orientation.w = msg.pose.orientation.w

    def vector2Arrays(self, vector):        
        return np.array([vector.x, vector.y, vector.z])

    def array2Vector3(self, array, vector):
        vector.x = array[0]
        vector.y = array[1]
        vector.z = array[2]

    def sigmoid(self, s, v):
        if np.absolute(s) > v:
            return s/np.absolute(s)
        else:
            return s/v

    def th_des(self):
        dt = rospy.get_time() - self.pre_time
        self.pre_time = self.pre_time + dt
        if dt > 0.04:
            dt = 0.04

        curPos = self.vector2Arrays(self.cur_pose.pose.position)
        desPos = self.vector2Arrays(self.sp.pose.position)
        curVel = self.vector2Arrays(self.cur_vel.twist.linear)

        errPos = curPos - desPos
        errVel = curVel - self.desVel
        # print(errPos)
        sv = errVel + np.multiply(self.Phi, errPos)

        if self.armed:
            self.Kp0 += (sv - np.multiply(self.alpha_0, self.Kp0))*dt
            self.Kp1 += (sv - np.multiply(self.alpha_1, self.Kp1))*dt
            self.Kp0 = np.maximum(self.Kp0, 0.0001*np.ones(3))
            self.Kp1 = np.maximum(self.Kp1, 0.0001*np.ones(3))
            # self.M += (-sv[2] - self.alpha_m*self.M)*dt
            # self.M = np.maximum(self.M, 0.1)
            # print(self.M)

        Rho = self.Kp0 + self.Kp1*errPos

        delTau = np.zeros(3)
        delTau[0] = Rho[0]*self.sigmoid(sv[0],self.v)
        delTau[1] = Rho[1]*self.sigmoid(sv[1],self.v)
        delTau[2] = Rho[2]*self.sigmoid(sv[2],self.v)

        des_th = -np.multiply(self.Lam, sv) - delTau + self.M*self.gravity
        # print((des_th))

        # self.array2Vector3(sv, self.data_out.sp)
        #self.array2Vector3(self.Kp0, self.data_out.Kp_hat)
        # self.array2Vector3(errPos, self.data_out.position_error)
        # self.array2Vector3(errVel, self.data_out.velocity_error)
        #self.array2Vector3(delTau, self.data_out.delTau_p)
        #self.array2Vector3(Rho, self.data_out.rho_p)
        #self.data_out.M_hat = self.M


        # putting limit on maximum thrust vector
        if np.linalg.norm(des_th) > self.max_th:
            des_th = (self.max_th/np.linalg.norm(des_th))*des_th

        return des_th

    def acc2quat(self, des_th, des_yaw):
        proj_xb_des = np.array([np.cos(des_yaw), np.sin(des_yaw), 0.0])
        if np.linalg.norm(des_th) == 0.0:
            zb_des = np.array([0,0,1])
        else:    
            zb_des = des_th / np.linalg.norm(des_th)
        yb_des = np.cross(zb_des, proj_xb_des) / np.linalg.norm(np.cross(zb_des, proj_xb_des))
        xb_des = np.cross(yb_des, zb_des) / np.linalg.norm(np.cross(yb_des, zb_des))
       
        rotmat = np.transpose(np.array([xb_des, yb_des, zb_des]))
        return rotmat

    def geo_con(self):
        des_th = self.th_des()    
        r_des = self.acc2quat(des_th, 0.0)
        rot_44 = np.vstack((np.hstack((r_des,np.array([[0,0,0]]).T)), np.array([[0,0,0,1]])))

        quat_des = quaternion_from_matrix(rot_44)
       
        zb = r_des[:,2]
        # thrust = self.norm_thrust_const * des_th.dot(zb)
        # self.data_out.thrust = thrust
        
        # thrust = np.maximum(0.0, np.minimum(thrust, self.max_throttle))

        now = rospy.Time.now()
        # self.data_out.header.stamp = now
        self.att_cmd.pose.orientation.x = quat_des[0]
        self.att_cmd.pose.orientation.y = quat_des[1]
        self.att_cmd.pose.orientation.z = quat_des[2]
        self.att_cmd.pose.orientation.w = quat_des[3]
        # self.thrust_cmd.thrust = thrust
        # print(thrust)
        # print(quat_des)

        # self.data_out.orientation = self.att_cmd.pose.orientation


    def geo_con_new(self):
        pose = transformations.quaternion_matrix(  
                numpy.array([self.cur_pose.pose.orientation.x, 
                             self.cur_pose.pose.orientation.y, 
                             self.cur_pose.pose.orientation.z, 
                             self.cur_pose.pose.orientation.w]))  #4*4 matrix
        pose_temp1 = np.delete(pose, -1, axis=1)
        rot_curr = np.delete(pose_temp1, -1, axis=0)   #3*3 current rotation matrix
        zb_curr = rot_curr[:,2]

        #---------------------------------------------#
        des_th = self.th_des()    
        rot_des = self.acc2quat(des_th, 0.0)   #desired yaw = 0

        thrust = self.norm_thrust_const * des_th.dot(zb_curr)
        thrust = np.maximum(0.0, np.minimum(thrust, self.max_throttle))
        self.thrust_cmd.thrust = thrust


        angle_error_matrix = 0.5 * (np.multiply(np.transpose(rot_des), rot_curr) -
                                    np.multiply(np.transpose(rot_curr), rot_des) ) #skew matrix
 
        roll_x_err = -angle_error_matrix[1,2]
        pitch_y_err = angle_error_matrix[0,2]
        yaw_z_err = -angle_error_matrix[0,1]

        self.euler_err = np.array([roll_x_err, pitch_y_err, yaw_z_err])

        self.des_q_dot = np.array([0 ,0, 0])
        des_euler_rate =  np.dot(np.multiply(np.transpose(rot_des), rot_curr), 
                                     self.des_q_dot)

        curr_euler_rate = np.array([self.cur_vel.twist.angular.x,
                                    self.cur_vel.twist.angular.y,
                                    self.cur_vel.twist.angular.z])

        self.euler_rate_err = curr_euler_rate - des_euler_rate

        # print(self.euler_err)
        # print(self.euler_rate_err)

        # print("-----------------")


    def moment_des(self):
        dt = rospy.get_time() - self.pre_time
        self.pre_time = self.pre_time + dt
        if dt > 0.04:
            dt = 0.04

        sv_q = self.euler_rate_err + np.multiply(self.Phi_q, self.euler_err)

        if self.armed:
            self.Kp0_q += (sv_q - np.multiply(self.alpha_0_q, self.Kp0_q))*dt
            self.Kp1_q += (sv_q - np.multiply(self.alpha_1_q, self.Kp1_q))*dt
            # self.Kp0_q = np.maximum(self.Kp0_q, 0.0001*np.ones(3))
            # self.Kp1_q = np.maximum(self.Kp1_q, 0.0001*np.ones(3))

        Rho_q = self.Kp0_q + self.Kp1_q*self.euler_err

        delTau_q = np.zeros(3)
        delTau_q[0] = Rho_q[0]*self.sigmoid(sv_q[0],self.v)
        delTau_q[1] = Rho_q[1]*self.sigmoid(sv_q[1],self.v)
        delTau_q[2] = Rho_q[2]*self.sigmoid(sv_q[2],self.v)

        des_mom = -np.multiply(self.Lam_q, sv_q) - delTau_q

    def pub_att(self):
        self.geo_con()
        self.thrust_pub.publish(self.thrust_cmd)
        self.att_pub.publish(self.att_cmd)
        # self.data_pub.publish(self.data_out)

        self.geo_con_new()