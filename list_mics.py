import speech_recognition as sr

mics = sr.Microphone.list_microphone_names()
for i, name in enumerate(mics):
    print(i, "-", name)
