@echo off
cd /d "C:\Users\Administrator\quant_futures"
if not exist "runtime\logs" mkdir "runtime\logs"
"C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe" -u "src\fengji_radar_order_loop.py" --data-dir data --symbols SA,FG,RB,PG,FU,CJ,OI,SP,LH,JD,SI,PP,SH,EB,NI,SR,EG,AO,JM,EC,RU,BR,SF,M,MA,P,V,TA,UR,CF,LC,AU,AG,SC --radar-dir runtime\fengji_radar --pending-dir runtime\fengji_pending_orders --loop-seconds 300 >> "runtime\logs\futures_radar_order_loop.log" 2>> "runtime\logs\futures_radar_order_loop_err.log"
