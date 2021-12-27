import datetime
import uuid

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Max, Min, Sum
from rest_framework import generics, serializers, status, permissions, views
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import Booking, Room
from .serializer import BookingSerializer, RoomSerializer

class RoomView(views.APIView):
    def get(self, request):
        rooms = Room.objects.all()
        return Response(rooms)

    def post(self, request):
        try:
            data = request.data
            room_name = data["room_name"]
            description = data["description"]

            if room_name is not None:
                room = Room.objects.create(
                    room_name=room_name, 
                    description=description,
                )       
                room.save()
                serializer = RoomSerializer(room, many=False)
                return Response({
                    'status': 'success',
                    'message': "room has been created",
                    'data': serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'status': 'failed',
                    'message': "None value for room_name is not acceptable",
                })

        except Exception as e:
            return Response({
                'status' : 'failed',
                'message': e
            })

class RoomFreeTime(views.APIView):
    def post(self, request):
        try:
            # date, roomID = request.data["date"], request.data["id"]
            # todayDate, todayTime = str(datetime.date.today()), datetime.datetime.today().time()

            # allBookingTime = Booking.objects.filter(
            #     booking_date__exact=date, room__exact=roomID
            # )


            res, date, roomID = [], request.data["date"], request.data["id"]
            for item in Booking.objects.filter(booking_date__exact=date, room__exact=roomID).order_by('start_timing', '-admin_did_accept', '-is_pending').distinct('start_timing'):

                x = {"start_timing": item.start_timing,
                     "end_timing": item.end_timing,
                     "admin_did_accept": item.admin_did_accept,
                     "is_pending": item.is_pending,
                    "availabel" : False
                     }
                res.append(x)
            # Create and append empty slots
            check = list()
            for i in res:
                check.append((i["start_timing"],i["end_timing"]))

            todayDate, todayTime = str(datetime.date.today()), datetime.datetime.today().time()

            buffer = datetime.timedelta(minutes=10)
            start = datetime.datetime(2000, 1, 1, 8, 0, 0)
            end = datetime.datetime(2000, 1, 1, 19, 00, 0)
            delta = datetime.timedelta(hours=1, minutes=30)

            while start <= end:
                if start.time() not in check[0]:
                    if todayDate == date and (start+buffer).time() <= todayTime:
                        start += delta
                        continue

                    if start.time().hour == 8:
                        y = {"start_timing": start.time(),
                            "end_timing": (start+delta).time(),
                            "admin_did_accept": False,
                            "is_pending": False,
                            "availabel": True
                            }
                    else:
                        y = {"start_timing": (start + buffer ).time(),
                            "end_timing": (start+delta).time(),
                            "admin_did_accept": False,
                            "is_pending": False,
                            "availabel": True
                            }

                    for time in check:
                        if time[1].hour == y["start_timing"].hour and time[1].minute > y["start_timing"].minute:
                            y["availabel"] = False
                        elif time[1].hour == y["end_timing"].hour and time[1].minute == y["end_timing"].minute:
                            print("check: ", time[1].hour, time[1].minute)
                            print("y: ", y["start_timing"].hour, y["start_timing"].minute)
                            y["start_timing"]
                            # y["availabel"] = False
                            y["end_timing"] = time[0] 
                        if time[0].hour == y["start_timing"].hour :
                            y["availabel"] = False

                    if y["availabel"] == True:
                        res.append(y)
                start += delta

                
            return Response(sorted(res, key=lambda i: i['start_timing']))

        except Exception as IndexError:
            return Response({"message": "no booking time is availabel"}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"message": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)




class BookRoomSlotView(views.APIView):
    startTimes = [datetime.time(8, 0), datetime.time(9, 30), datetime.time(11, 0), datetime.time(13, 0), datetime.time(14, 30), datetime.time(16, 0), datetime.time(17, 30), datetime.time(19, 0)]
    endTimes = [datetime.time(9, 30), datetime.time(11, 0), datetime.time(12, 30), datetime.time(14, 30), datetime.time(16, 0), datetime.time(17, 30), datetime.time(19, 0), datetime.time(20, 30)]

    parser_classes = [JSONParser]

    def post(self, request):
        try:
            res, data = [], request.data
            try:
                purpose = data["purpose_of_booking"]
            except:
                purpose = "Purpose not provided"
            start = datetime.datetime.strptime(data["startTime"],"%H:%M:%S").time()
            end = datetime.datetime.strptime(data["endTime"], "%H:%M:%S").time()
            print(start)
            roomId, date = data["id"], data["date"]
            # if (start not in BookRoomSlotView.startTimes) or (end not in BookRoomSlotView.endTimes):
            #     return Response("This slot does not exist. Booking not possible")

            if Booking.objects.filter(booking_date__exact=date, start_timing=start, end_timing=end).exclude(admin_did_accept=False, is_pending=False).count() >= 1:
                return Response("You have already booked this timing. You cannot book 2 slots at the same time", status.HTTP_409_CONFLICT)
            
            for item in Booking.objects.filter(booking_date__exact=date, room__exact=roomId):
                if (end <= item.start_timing or start >= item.end_timing):
                    # no clashes if the entire for loop doesn't break then the following else is executed
                    continue
                elif (item.admin_did_accept == True):
                    # Already booked
                    return Response("This slot has already been booked", status=status.HTTP_306_RESERVED)
                else:
                    # empty slot with many bookings
                    room = Room.objects.get(id__exact=roomId)
                    b = Booking.objects.create(room=room, booking_date=date, start_timing=start, end_timing=end, purpose_of_booking=purpose, is_pending=True)
                    return Response("Booking has been added to the already existing queue", status=status.HTTP_202_ACCEPTED)
            else:
                # no clashes executed if for loop doesnt  break
                room = Room.objects.get(id__exact=roomId)
                b = Booking.objects.create(room=room, booking_date=date, start_timing=start, end_timing=end, purpose_of_booking=purpose, is_pending=True)
                return Response("Booking has been added to the queue", status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"message": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)


class UserPastBookingsView(views.APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        slot = Booking.objects.filter(booking_date__lte=datetime.date.today())
        res = []
        for item in slot.filter(booking_date__lt=datetime.date.today()).union(slot.filter(booking_date__exact=datetime.date.today(), end_timing__lt=datetime.datetime.now().time())):
            x = {"booking_date": item.booking_date,
                 "start_timing": item.start_timing,
                 "end_timing": item.end_timing,
                 "admin_did_accept": item.admin_did_accept,
                 "is_pending": item.is_pending,
                 "purpose_of_booking": item.purpose_of_booking,
                 "admin_feedback": item.admin_feedback,
                 "room_name": item.room.room_name
                 }
            res.append(x)
        return Response(sorted(res, key=lambda i: i['start_timing']))



class AllBookingView(views.APIView):
    def get(self, request):
        bookings = Booking.objects.all()
        return Response(bookings)


