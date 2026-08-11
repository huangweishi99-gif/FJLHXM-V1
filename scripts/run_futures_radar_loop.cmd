@echo off
cd /d "C:\Users\Administrator\quant_futures"
if not exist "runtime\logs" mkdir "runtime\logs"
"C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe" -u "src\fengji_radar_order_loop.py" --market futures --data-dir data --symbols SA,FG,RB,PG,FU,CJ,OI,SP,LH,JD,SI,PP,SH,EB,NI,SR,EG,AO,JM,EC,RU,BR,SF,M,MA,P,V,TA,UR,CF,LC,AU,AG,SC --radar-dir runtime\fengji_radar --pending-dir runtime\fengji_pending_orders --monitor-state runtime\fengji_pending_orders\futures_pending_state.json --include-triggered --loop-seconds 600 --daily-tail 400 --h1-tail 2400 --m15-tail 960 --top-n 40 >> "runtime\logs\futures_radar_order_loop.log" 2>> "runtime\logs\futures_radar_order_loop_err.log"
