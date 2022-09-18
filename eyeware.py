'''
Display a gaze marker on the camera/scene video. Demonstrates how to receive frames from the camera, map gaze data onto
a camera frame, and draw a gaze marker.
'''

import math
import sys
import cv2
import numpy as np
import imutils
from playsound import playsound
import multiprocessing

from Pedestrian_detection import *
from Pedestrian_tracking import *

import adhawkapi
import adhawkapi.frontend
from adhawkapi import MarkerSequenceMode, PacketType


MARKER_SIZE = 5  # Diameter in pixels of the gaze marker
MARKER_COLOR = (0, 250, 50)  # Colour of the gaze marker

SECONDARY_MARKER_SIZE = 20
SECONDARY_MARKER_COLOR = (250, 0, 0, 64)


FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.5
TEXT_ORG = (50,50)
TEXT_COLOR = (0,0,255)
TEXT_THICKNESS = 2


play_sound = False

class Frontend:
    ''' Frontend communicating with the backend '''

    def __init__(self, handle_gaze_in_image_stream, video_receiver_address):
        # Instantiate an API object
        self._api = adhawkapi.frontend.FrontendApi()

        # Tell the api that we wish to tap into the GAZE_IN_IMAGE data stream with the given callback as the handler
        self._api.register_stream_handler(PacketType.GAZE_IN_IMAGE, handle_gaze_in_image_stream)

        # Start the api and set its connection callback to self._handle_connect. When the api detects a connection to a
        # tracker, this function will be run.
        self._api.start(connect_cb=self._handle_connect_response)

        # Stores the video receiver's address
        self._video_receiver_address = video_receiver_address

        # Flags the frontend as not connected yet
        self.connected = False

    def shutdown(self):
        ''' Shuts down the backend connection '''

        # Stops the video stream
        self._api.stop_video_stream(*self._video_receiver_address, lambda *_args: None)

        # Stops api camera capture
        self._api.stop_camera_capture(lambda *_args: None)

        # Stop the log session
        self._api.stop_log_session(lambda *_args: None)

        # Shuts down the api
        self._api.shutdown()

    def _handle_connect_response(self, error):

        # Starts the camera and sets the stream rate
        if not error:

            # Sets the GAZE_IN_IMAGE data stream rate to 125Hz
            self._api.set_stream_control(PacketType.GAZE_IN_IMAGE, 125, callback=(lambda *args: None))

            # Starts the tracker's camera so that video can be captured and sets self._handle_camera_start_response as
            # the callback. This function will be called once the api has finished starting the camera.
            self._api.start_camera_capture(camera_index=1, resolution_index=adhawkapi.CameraResolution.MEDIUM,
                                           correct_distortion=False, callback=self._handle_camera_start_response)

            # Starts a logging session which saves eye tracking signals. This can be very useful for troubleshooting
            self._api.start_log_session(log_mode=adhawkapi.LogMode.BASIC, callback=lambda *args: None)

            # Flags the frontend as connected
            self.connected = True

    def _handle_camera_start_response(self, error):

        # Handles the response after starting the tracker's camera
        if error:
            # End the program if there is a camera error
            print(f'Camera start error: {error}')
            self.shutdown()
            sys.exit()
        else:
            # Otherwise, starts the video stream, streaming to the address of the video receiver
            self._api.start_video_stream(*self._video_receiver_address, lambda *_args: None)


class GazeViewer():
    ''' Class for receiving and displaying the video stream '''

    def __init__(self):
        # Instantiate and start a video receiver with self._handle_video_stream as the handler for new frames
        self._video_receiver = adhawkapi.frontend.VideoReceiver()
        self._video_receiver.frame_received_event.add_callback(self._handle_video_stream)
        self._video_receiver.start()

        # Instantiate a Frontend object. We give it the address of the video receiver, so the api's video stream will
        # be sent to it.
        self.frontend = Frontend(self._handle_gaze_in_image_stream, self._video_receiver.address)

        # Initialize the gaze coordinates to dummy values for now
        self._gaze_coordinates = (0, 0)

        self.ct = CentroidTracker()

    def closeEvent(self, event):
        '''
        Override of the window's close event. When the window closes, we want to ensure that we shut down the api
        properly.
        '''
        self.frontend.shutdown()

    def close(self):
        self.frontend.shutdown()
        cv2.destroyAllWindows()

    @property
    def connected(self):
        ''' Property to allow the main loop to check whether the api is connected to a tracker '''
        return self.frontend.connected

    def _handle_video_stream(self, _gaze_timestamp, _frame_index, image_buf, _frame_timestamp):
        np_arr = np.frombuffer(image_buf, np.uint8)
        image = cv2.imdecode(np_arr, 1)

        # Your code here
        image = imutils.resize(image, width=640)
        results = pedestrian_detection(image, model, layer_name,
            personidz=LABELS.index("person"))
        
        # for res in results:
            # rects.append(res)
            # cv2.rectangle(image, (res[1][0],res[1][1]), (res[1][2],res[1][3]), (0, 255, 0), 2)
        play_sound = False
        objects = self.ct.update(results)
        # loop over the tracked objects
        for (objectID, person) in objects.items():
            # draw both the ID of the object and the centroid of the
            # object on the output frame
            text = "ID {}".format(objectID)
            cv2.putText(image, text, (person.centroid[0] - 10, person.centroid[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.circle(image, (person.centroid[0], person.centroid[1]), 4, (0, 255, 0), -1)

            # put seen / not seen logic here
            if (person.is_seen):
                cv2.rectangle(image, (person.rect[1][0],person.rect[1][1]), (person.rect[1][2],person.rect[1][3]), (0, 255, 0), 2)

            elif (not person.is_person_seen(self._gaze_coordinates)):
                if (person.is_person_close):
                    cv2.rectangle(image, (person.rect[1][0],person.rect[1][1]), (person.rect[1][2],person.rect[1][3]), (255, 0, 0), 2) #R
                    play_sound = True
                else:
                    cv2.rectangle(image, (person.rect[1][0],person.rect[1][1]), (person.rect[1][2],person.rect[1][3]), (255, 255, 0), 2)

            else:
                cv2.rectangle(image, (person.rect[1][0],person.rect[1][1]), (person.rect[1][2],person.rect[1][3]), (0, 255, 0), 2)

            

        image = cv2.putText(
            image,
            f"{self._gaze_coordinates[0]}, {self._gaze_coordinates[1]}",
            TEXT_ORG,
            FONT,
            FONT_SCALE,
            TEXT_COLOR,
            TEXT_THICKNESS,
            cv2.LINE_AA
        )


        if not (math.isnan(self._gaze_coordinates[0]) or math.isnan(self._gaze_coordinates[1])):
            fixed_gaze_coords = (int(self._gaze_coordinates[0]/1280 * 640), int(self._gaze_coordinates[1]/720 * 360))

            cv2.circle(image, fixed_gaze_coords, MARKER_SIZE, MARKER_COLOR, 2)
            cv2.circle(image, fixed_gaze_coords, SECONDARY_MARKER_SIZE, SECONDARY_MARKER_COLOR, 2)

        cv2.imshow("preview", image)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.close()


    def _handle_gaze_in_image_stream(self, _timestamp, gaze_img_x, gaze_img_y, *_args):
        self._gaze_coordinates = [gaze_img_x, gaze_img_y]

    def _draw_gaze_marker(self, qt_img):
        pass

def play_warning_sound():
    p = multiprocessing.Process(target=playsound, args=("/sound/soundeffect.mp3",))
    if (play_sound):
        p.start()
    else:
        p.terminate()



def main():
    '''Main function'''
    main_window = GazeViewer()
    play_warning_sound()
    try:
        print('Plug in your tracker and ensure AdHawk Backend is running.')
        while not main_window.connected:
            pass  # Waits for the frontend to be connected before proceeding
    except (KeyboardInterrupt, SystemExit):
        main_window.close()
        # Allows the frontend to be shut down robustly on a keyboard interrupt

    

if __name__ == '__main__':
    main()
