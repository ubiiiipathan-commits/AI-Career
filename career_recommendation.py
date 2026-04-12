def recommend_careers(text):

    text = text.lower()

    # Skill List
    skill_list = [
        "python","java","c++","sql","machine learning","deep learning",
        "data analysis","pandas","numpy","tensorflow","html","css",
        "javascript","flask","django","power bi","excel","tableau",
        "accounting","finance","tally","marketing","sales","hr","management"
    ]

    detected_skills = []

    for skill in skill_list:
        if skill in text:
            detected_skills.append(skill.title())

    # Career + Courses

    if "accounting" in text or "finance" in text or "tally" in text:
        career = "Accountant"
        courses = ["Tally ERP", "Accounting", "GST"]

    elif "marketing" in text or "sales" in text:
        career = "Marketing Executive"
        courses = ["Digital Marketing", "SEO", "Marketing Strategy"]

    elif "hr" in text or "human resource" in text:
        career = "HR Manager"
        courses = ["HR Management", "Recruitment", "Payroll"]

    elif "business" in text or "management" in text:
        career = "Business Analyst"
        courses = ["Business Analysis", "Excel", "Data Visualization"]

    elif "machine learning" in text or "python" in text:
        career = "Data Scientist"
        courses = ["Machine Learning", "Python", "Data Analysis"]

    elif "html" in text or "css" in text or "javascript" in text:
        career = "Web Developer"
        courses = ["HTML", "CSS", "JavaScript"]

    elif "sql" in text or "excel" in text:
        career = "Data Analyst"
        courses = ["SQL", "Excel", "Power BI"]

    else:
        career = "Software Developer"
        courses = ["Python", "DSA", "Software Engineering"]

    return career, detected_skills, courses