#! /usr/bin/env python

import os
import time
import datetime
from types import *
from libraries import apptest
from libraries import rgt_utilities
#
# Author: Arnold Tharrington  (arnoldt@ornl.gov)
# National Center for Computational Sciences, Scientific Computing Group.
# Oak Ridge National Laboratory
#

class run_me:

    #These strings define the tasks that the tests can do.
    checkout = "check_out_tests"
    starttest = "start_tests"
    stoptest = "stop_tests"
    displaystatus = "display_status"
    summarize_results = "summarize_results"
    status_file = "applications_status.txt"


    def __init__(self,rgt_input_file):
        self.__tests = rgt_input_file.get_tests()
        self.__tasks = rgt_input_file.get_harness_tasks()
        self.__local_path_to_tests = rgt_input_file.get_local_path_to_tests()
        self.__appsubtest = []
        mycomputer_with_events_record = None

        #Make instances of each test/subtest
        for test in self.__tests:
            #Instantiate an instance of the test.
            self.__appsubtest  = self.__appsubtest + [apptest.subtest(name_of_application=test[0],
                                                      name_of_subtest=test[1],
                                                      local_path_to_tests=self.__local_path_to_tests,
                                                      number_of_iterations=test[2]) ]

        #Perform the tasks for each test.
        for appsubtest1 in self.__appsubtest:

            #Perform each task
            for taskwords in self.__tasks:
                task = None
                if type(taskwords) == ListType:
                    task = taskwords[0]
                    if mycomputer_with_events_record == None:
                       mycomputer_with_events_record = rgt_utilities.return_my_computer_with_events_record(taskwords[1:])
                else:
                    task = taskwords

                if task == run_me.checkout:
                    self.__check_out_test(appsubtest1)

                if task == run_me.starttest:
                    self.__start_test(appsubtest1)

                if task == run_me.stoptest:
                   self.__stop_test(appsubtest1)

                if (task == run_me.displaystatus) and (type(taskwords) == ListType):
                    self.__display_status(appsubtest1,taskwords[1:],mycomputer_with_events_record)
                elif (task == run_me.displaystatus):
                    self.__display_status(appsubtest1,None,None)


        #Special code block for summarizing results.
        for taskwords in self.__tasks:
            task = None
            if type(taskwords) == ListType:
                task = taskwords[0]
                if mycomputer_with_events_record == None:
                   mycomputer_with_events_record = rgt_utilities.return_my_computer_with_events_record(taskwords[1:])

                # Do job summary task. 
                if task == run_me.summarize_results:
                    self.__summarize_results(taskwords[1:],mycomputer_with_events_record)
                    

    def __check_out_test(self,apptest1):
        # Check out the files.
        apptest1.check_out_test()

    def __start_test(self,apptest1):
        #Start the test.
        apptest1.start_test()

    def __stop_test(self,apptest1):
        #Stop the test.
        apptest1.stop_test()

    def __display_status(self,apptest1,taskwords,mycomputer_with_events_record):
        #Display the test status.
        print "In display_status"
        if mycomputer_with_events_record == None:
            apptest1.display_status()
        else:
            apptest1.display_status2(taskwords,mycomputer_with_events_record)

    def __summarize_results(self,taskwords,mycomputer_with_events_record):
        failed_list = []
        inconclusive_list = []
        results = {"Test_has_at_least_1_pass" : 0,
                   "Number_attemps" : 0,
                   "Number_passed" : 0,
                   "Number_failed" : 0,
                   "Number_inconclusive" : 0,
                   "Failed_jobs" : [] ,
                   "Inconclusive_jobs" : []}

        #-----------------------------------------------------
        #                                                    -
        #                                                    -
        #-----------------------------------------------------
        tests_with_no_passes = []

        #-----------------------------------------------------
        # Generate a time stamp of the current time.         -
        #                                                    -
        #-----------------------------------------------------
        currenttime = time.localtime()
        timestamp = time.strftime("%Y%b%d_%H:%M:%S",currenttime)

        #-----------------------------------------------------
        # Generate the name of the logfile.                  -
        #                                                    -
        #-----------------------------------------------------
        logfile = run_me.status_file + "__" + str(timestamp)
        for appsubtest1 in self.__appsubtest:
            app_status = appsubtest1.generateReport(logfile,taskwords,mycomputer_with_events_record)

            if app_status["Number_passed"] == 0:
                tests_with_no_passes = tests_with_no_passes + [appsubtest1.name()]

            if app_status["Number_failed"] > 0:
               for tmpjob in app_status["Failed_jobs"]:
                    print "Failed job: ", tmpjob

            if app_status["Number_inconclusive"] > 0:
               for tmpjob in app_status["Inconclusive_jobs"]:
                    print "Inconclusive job: ", tmpjob


            for key in app_status.keys():
                results[key] = results[key] + app_status[key]

        dfile_obj = open(logfile,"a")
        dfile_obj.write("\n\n\nTest with 0 passes\n")
        dfile_obj.write("==================\n")
        for [application,subtest] in tests_with_no_passes:
            appname = "{app:20s} {test:20s}\n".format(app=application,test=subtest)
            dfile_obj.write(appname)

        dfile_obj.write("\n\n\nSummary\n")
        dfile_obj.write("==================\n")
        tmp_string = "Number of attempts = {attemps:10s}\n".format(attemps=str(results["Number_attemps"]))
        dfile_obj.write(tmp_string)
        tmp_string = "Number of passes = {passes:10s}\n".format(passes=str(results["Number_passed"]))
        dfile_obj.write(tmp_string)
        tmp_string = "Number of fails = {fails:10s}\n".format(fails=str(results["Number_failed"]))
        dfile_obj.write(tmp_string)
        tmp_string = "Number inconclusive = {inconclusive:10s}\n".format(inconclusive=str(results["Number_inconclusive"]))
        dfile_obj.write(tmp_string)

        dfile_obj.close()