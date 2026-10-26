"""Predefined Question Bank for Vani 2.0 POC.

Stores exactly two predefined questions per skill for:
- Python
- SQL
- Java
- Machine Learning
"""

from typing import Dict, List

PREDEFINED_QUESTIONS: Dict[str, List[Dict[str, object]]] = {
    "Python": [
        {
            "question_id": "py_q1",
            "text": "What is the difference between a list and a tuple in Python, and when would you use each?",
            "skills": ["Python"]
        },
        {
            "question_id": "py_q2",
            "text": "How would you handle exceptions when reading a file in Python?",
            "skills": ["Python"]
        }
    ],
    "SQL": [
        {
            "question_id": "sql_q1",
            "text": "How would you write a SQL query to find the second-highest salary in an employee table?",
            "skills": ["SQL"]
        },
        {
            "question_id": "sql_q2",
            "text": "What is the difference between an INNER JOIN and a LEFT JOIN?",
            "skills": ["SQL"]
        }
    ],
    "Java": [
        {
            "question_id": "java_q1",
            "text": "What is the difference between an interface and an abstract class in Java?",
            "skills": ["Java"]
        },
        {
            "question_id": "java_q2",
            "text": "Explain how exception handling works in Java and when you would use a finally block?",
            "skills": ["Java"]
        }
    ],
    "Machine Learning": [
        {
            "question_id": "ml_q1",
            "text": "What is the difference between supervised and unsupervised learning?",
            "skills": ["Machine Learning"]
        },
        {
            "question_id": "ml_q2",
            "text": "What is overfitting in machine learning, and how can you reduce it?",
            "skills": ["Machine Learning"]
        }
    ]
}
