'''
Display a gaze marker on the camera/scene video. Demonstrates how to receive frames from the camera, map gaze data onto
a camera frame, and draw a gaze marker.
'''

import math
import sys
import cv2
import numpy as np

import adhawkapi
import adhawkapi.frontend
from adhawkapi import MarkerSequenceMode, PacketType


MARKER_SIZE = 20  # Diameter in pixels of the gaze marker
MARKER_COLOR = (0, 250, 50)  # Colour of the gaze marker

SECONDARY_MARKER_SIZE = 200
SECONDARY_MARKER_COLOR = (250, 0, 0, 64)


FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 1
TEXT_ORG = (50,50)
TEXT_COLOR = (0,0,255)
TEXT_THICKNESS = 2


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

        cv2.imshow("preview", image)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            self.close()

        print(self._gaze_coordinates)


    def _handle_gaze_in_image_stream(self, _timestamp, gaze_img_x, gaze_img_y, *_args):
        self._gaze_coordinates = [gaze_img_x, gaze_img_y]

    def _draw_gaze_marker(self, qt_img):
        pass


def main():
    '''Main function'''
    main_window = GazeViewer()
    try:
        print('Plug in your tracker and ensure AdHawk Backend is running.')
        while not main_window.connected:
            pass  # Waits for the frontend to be connected before proceeding
    except (KeyboardInterrupt, SystemExit):
        main_window.close()
        # Allows the frontend to be shut down robustly on a keyboard interrupt

    

if __name__ == '__main__':
    main()
