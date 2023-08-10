#!/usr/bin/env python
# coding: utf-8
"""
Detect Objects Using Your Webcam
================================
"""
import os
import cv2
import pytesseract
import re
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'    # Suppress TensorFlow logging
import tensorflow as tf
from object_detection.utils import label_map_util
from object_detection.utils import config_util
from object_detection.utils import visualization_utils as viz_utils
from object_detection.builders import model_builder
import parking
import time
connection_string = 'Driver={SQL Server};Server=GEO;Database=parking;Trusted_Connection=yes;'
parking_meter = parking.ParkingMeter(connection_string)

tf.get_logger().setLevel('ERROR')           # Suppress TensorFlow logging (2)
PATH_TO_MODEL_DIR = 'C:\\Users\\georg\\OneDrive\\Desktop\\TensorFlow\\workspace\\training_demo\\exported-models\\my_model'
PATH_TO_SAVED_MODEL = PATH_TO_MODEL_DIR + "/saved_model"

# Enable GPU dynamic memory allocation
gpus = tf.config.experimental.list_physical_devices('GPU')
for gpu in gpus:
    tf.config.experimental.set_memory_growth(gpu, True)


detection_model = tf.saved_model.load(PATH_TO_SAVED_MODEL)

PATH_TO_LABELS = 'C:\\Users\\georg\\OneDrive\\Desktop\\TensorFlow\\workspace\\training_demo\\annotations\\label_map.pbtxt'
import numpy as np

def recognize_plate(img, coords):
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    cv2.imwrite("img.png", img)
    if img is None or img.size == 0:
        print("Input image is empty or None.")
        return ""
    
    roi_list = []

    ymin, xmin, ymax, xmax = coords
    box = img[int(ymin):int(ymax), int(xmin):int(xmax)]  # Removed extra padding
  #  cv2.imwrite("1_box.png", box)

    if box is None or box.size == 0:
        print("Bounded region is empty.")
        return ""

    gray = cv2.cvtColor(box, cv2.COLOR_RGB2GRAY)
  #  cv2.imwrite("2_gray.png", gray)

    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
  #  cv2.imwrite("3_resize.png", gray)

    blur = cv2.GaussianBlur(gray, (5, 5), 0)
  #  cv2.imwrite("4_blur.png", blur)

    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_OTSU | cv2.THRESH_BINARY_INV)

    rect_kern = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilation = cv2.dilate(thresh, rect_kern, iterations=1)
   # cv2.imwrite("5_dilation.png", dilation)

    try:
        contours, _ = cv2.findContours(dilation, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    except:
        _, contours, _ = cv2.findContours(dilation, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    sorted_contours = sorted(contours, key=lambda ctr: cv2.boundingRect(ctr)[0])

    im2 = gray.copy()
    plate_num = ""

    for idx, cnt in enumerate(sorted_contours):
        x, y, w, h = cv2.boundingRect(cnt)
        height, _ = im2.shape

        if height / float(h) > 6:
            continue

        ratio = h / float(w)

        if ratio < 1.5:
            continue

        area = h * w

        if area < 100:
            continue

        roi = thresh[y:y+h, x:x+w]
        roi = cv2.bitwise_not(roi)
        roi = cv2.medianBlur(roi, 5)

        if roi is not None and roi.size != 0:
          #  cv2.imwrite(f'{idx}.jpg',roi)
            roi_list.append(roi)
            
    if roi_list:
        max_height = max([roi.shape[0] for roi in roi_list])
        roi_list_resized = [cv2.resize(roi, (roi.shape[1], max_height)) for roi in roi_list]
        combined_roi = np.hstack(roi_list_resized)  # Horizontally stack the resized ROIs
        #blurred = cv2.GaussianBlur(combined_roi, (3, 3), 0)
       # sharpened = cv2.addWeighted(combined_roi, 2.0, blurred, -0.5, 0)

     #   cv2.imwrite("roi.jpg", combined_roi)  # Save the combined ROI as an image file

        try:
            text = pytesseract.image_to_string(combined_roi, config='-c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ --psm 7 --oem 3')
            clean_text = re.sub('[\W_]+', '', text)
            print("License Plate #: ", clean_text)
            return clean_text
        except Exception as e:
            print("Tesseract error:", e)

    if plate_num:
        print("License Plate #: ", plate_num)
        
    return plate_num




# %%
# Load label map data (for plotting)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Label maps correspond index numbers to category names, so that when our convolution network
# predicts `5`, we know that this corresponds to `airplane`.  Here we use internal utility
# functions, but anything that returns a dictionary mapping integers to appropriate string labels
# would be fine.
category_index = label_map_util.create_category_index_from_labelmap(PATH_TO_LABELS,
                                                                    use_display_name=True)

# %%
# Define the video stream
# ~~~~~~~~~~~~~~~~~~~~~~~
# We will use `OpenCV <https://pypi.org/project/opencv-python/>`_ to capture the video stream
# generated by our webcam. For more information you can refer to the `OpenCV-Python Tutorials <https://opencv-python-tutroals.readthedocs.io/en/latest/py_tutorials/py_gui/py_video_display/py_video_display.html#capture-video-from-camera>`_
import cv2

cap = cv2.VideoCapture(1)

# %%
# Putting everything together
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~
# The code shown below loads an image, runs it through the detection model and visualizes the
# detection results, including the keypoints.
#
# Note that this will take a long time (several minutes) the first time you run this code due to
# tf.function's trace-compilation --- on subsequent runs (e.g. on new images), things will be
# faster.
#
# Here are some simple things to try out if you are curious:
#
# * Modify some of the input images and see if detection still works. Some simple things to try out here (just uncomment the relevant portions of code) include flipping the image horizontally, or converting to grayscale (note that we still expect the input image to have 3 channels).
# * Print out `detections['detection_boxes']` and try to match the box locations to the boxes in the image.  Notice that coordinates are given in normalized form (i.e., in the interval [0, 1]).
# * Set ``min_score_thresh`` to other values (between 0 and 1) to allow more detections in or to filter out more detections.
import numpy as np
active_vehicles = {}
MINIMUM_PARKING_TIME = 0  # Minimum parking time in seconds (e.g., 5 minutes)
# Number of consecutive consistent readings to trigger car_seen
consistent_readings_threshold = 1
last_plate_numbers = []  # Queue to store the last consistent readings

while True:
    # Read frame from camera
    ret, image_np = cap.read()
    image_np = cv2.resize(image_np, (640, 640))

    image_np = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)

    input_tensor = tf.convert_to_tensor(image_np)
    input_tensor = input_tensor[tf.newaxis, ...]

    detections = detection_model(input_tensor)
    num_detections = int(detections.pop('num_detections'))
    detections = {key: value[0, :num_detections].numpy()
                   for key, value in detections.items()}
    detections['num_detections'] = num_detections
    detections['detection_classes'] = detections['detection_classes'].astype(np.int64)
    image_np_with_detections = image_np.copy()

    viz_utils.visualize_boxes_and_labels_on_image_array(
          image_np_with_detections,
          detections['detection_boxes'],
          detections['detection_classes'],
          detections['detection_scores'],
          category_index,
          use_normalized_coordinates=True,
          max_boxes_to_draw=1,
          min_score_thresh=.30,
          agnostic_mode=False)

    bboxes = detections['detection_boxes']
    scores = detections['detection_scores']
    classes = detections['detection_classes']
    num_detections = detections['num_detections']

    # Convert normalized bounding box to original image coordinates
    original_h, original_w, _ = image_np.shape
    bbox = bboxes[0] * [original_h, original_w, original_h, original_w]

    # Convert the bounding box and score to lists
    bbox = bbox.tolist()

    height_ratio = int(original_h / 25)
    plate_number = recognize_plate(image_np, bbox)
    if plate_number!="":
        cv2.putText(image_np_with_detections, plate_number, (int(bbox[1]), int(bbox[0]-height_ratio)), 
            cv2.FONT_HERSHEY_SIMPLEX, 1.25, (255,255,0), 2)
        # Check if the last N readings were consistent

        parking_meter.car_seen(plate_number)

    # Display output
    image_np_with_detections = cv2.cvtColor(image_np_with_detections, cv2.COLOR_RGB2BGR)

    cv2.imshow('object detection', image_np_with_detections)

    if cv2.waitKey(25) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()