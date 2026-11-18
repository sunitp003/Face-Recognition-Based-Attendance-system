"""Server-side attendance subject catalogue. Keep aligned with static/js/attendance_subjects.js."""
SUBJECTS = {
 "ce": {"1": ("M1","M2","Physics","Chemistry"), "2": ("M3","DSA","COA","DBMS"), "3": ("OS","CN","TOC","SE"), "4": ("AI","ML","Cloud Computing","Big Data")},
 "it": {"1": ("M1","M2","Physics","Chemistry"), "2": ("DSA","OOPS","DBMS","Computer Networks"), "3": ("OS","Web Technologies","AI","Cybersecurity"), "4": ("Blockchain","IoT","Data Science","DevOps")},
 "me": {"1": ("Engineering Mechanics","M1","Physics","Chemistry"), "2": ("Thermodynamics","Fluid Mechanics","SOM","Material Science"), "3": ("Manufacturing","IC Engines","Robotics","Heat Transfer"), "4": ("Automobile Engineering","Mechatronics","Advanced Robotics","Computational Fluid Dynamics")},
 "ec": {"1": ("M1","M2","Physics","Chemistry"), "2": ("Digital Electronics","Microprocessors","Signals & Systems","Communication Networks"), "3": ("Embedded Systems","VLSI","Wireless Communication","DSP"), "4": ("IoT","Optical Fiber Communication","Radar Systems","Satellite Communication")},
 "ee": {"1": ("Electrical Circuits","Maths","Physics"), "2": ("Machines","Power Systems","Electromagnetics"), "3": ("Control Systems","Power Electronics","Energy Management"), "4": ("Smart Grid","Renewable Energy","High Voltage Engineering")},
}


def is_valid_subject(branch, year, subject):
    """Only allow subjects present in the server-side branch/year catalogue."""
    return (isinstance(branch, str) and isinstance(year, str) and isinstance(subject, str)
            and subject in SUBJECTS.get(branch.strip().lower(), {}).get(year.strip(), ()))
