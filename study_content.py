"""Participant-facing study text copied from the Method stimuli supplement."""

SESSION_INTRODUCTION = """
In this study, you will complete two connected learning activities about research design. In one activity, you will work through a research problem and develop possible study ideas. In the other activity, you will read a short lesson about the same research problem and a clear experimental-design approach. Please work carefully through each activity, even when you are still unsure which study ideas are strongest.
"""

INSTRUCTION_ENTRY = """
You are now starting the first learning activity. In this activity, you will read a short lesson about a research-design problem, common weaknesses in first study ideas, and a clear experimental-design approach. Read it carefully, because it will help you think about how competing explanations can be tested.
"""

PROBLEM_SOLVING_ENTRY = """
You are now starting the first learning activity. In this activity, you will work through a research-design problem and develop possible study ideas. You will discuss the problem with an AI discussion partner. It will ask questions, respond to your ideas, and help you consider different possibilities, but it will not provide a completed study design for you. Try to propose several different study ideas.
"""

INSTRUCTION_TO_PROBLEM_SOLVING_TRANSITION = """
You will now continue to the second learning activity. In the activity you just completed, you read about the research problem and one clear experimental-design approach. In the next activity, you will discuss the same research problem with an AI discussion partner and develop possible study ideas.
"""

PROBLEM_SOLVING_TO_INSTRUCTION_TRANSITION = """
You will now continue to the second learning activity. In the activity you just completed, you discussed possible ways to test the researchers' suggestions. In the next activity, you will read a short lesson that returns to the same problem, compares common first study ideas with stronger design choices, and presents a clear experimental-design approach.
"""

SHARED_PROBLEM_BACKGROUND = """
**How should researchers test whether social media use increases anxiety?**

At a research meeting in the Department of Communication Science, several researchers discuss recent reports that students who use social media heavily often report higher anxiety. The researchers agree that this issue matters, but they disagree about why this pattern appears and how it should be studied.

**Dr. De Jong**

"I think the main issue is the amount of social media use. Students who spend more time on social media are likely to feel more anxious than students who spend less time on it."

**Dr. Jansen**

"Time may matter, but I think the type of use is also important. Passive scrolling may be more harmful than active use, such as posting, commenting, or messaging. I am not sure whether heavy use is equally harmful across different usage modes."

**Dr. De Vries**

"Both points may matter, but some students are already under more academic stress than others. If we do not measure this, we may draw the wrong conclusion about the effect of social media use itself."

The research coordinator thinks that all three researchers have raised important points. The coordinator wants to test the different ideas and opinions in a study, but does not know how to conduct such a study, which data should be collected, or what the procedure should be. The coordinator is searching for an appropriate study design that investigates all stated ideas and opinions.
"""

PROBLEM_SOLVING_TASK_PROMPT = """
That is why the research coordinator is asking you for help.

**This is your task:**

You are communication researchers and are asked to think about how it would be possible to investigate and test which of the researchers' stated opinions and suggestions are best supported. What might appropriate studies look like? Generate as many study ideas as possible and describe them in writing.

Good luck and do not give up until you have proposed several ways to test the different suggestions!
"""

PROBLEM_SOLVING_INSTRUCTIONS = """
- Use the chat to think through the problem step by step.
- The AI discussion partner may ask questions and point out issues your current ideas do not yet address.
- The AI discussion partner will not provide a final study design for you.
- Do not enter your name, email address, phone number, student number, or other identifying information in the chat or in the `Study ideas to submit` box.
- In the `Study ideas to submit` box, describe the study ideas you want to submit.
"""

PROBLEM_SOLVING_CHAT_INSTRUCTION = """
Please work through the problem with the AI discussion partner before submitting your study ideas. The option to end the chat will appear after you have sent at least five messages to the AI discussion partner.
"""

STUDY_IDEAS_SAVE_NOTE = (
    "This box is only for this learning activity. You do not need to save the text; "
    "when you are ready, continue to the next step."
)

SHOW_FULL_RESEARCH_PROBLEM_LABEL = "Show full research problem"

COPY_STUDY_DATA_INSTRUCTION = (
    "Use the copy button in the Study data to copy box below. If the button does "
    "not work, select the text in that same box and copy it manually. Then "
    "return to Qualtrics and paste it into the survey box."
)

INSTRUCTION_FIRST_STIMULUS_OPENING = """
In this lesson, you will work with the research problem about social media use and anxiety that you just read about. Several communication researchers have different ideas about why students who use social media heavily may report higher anxiety.

The goal is not to decide which researcher sounds most convincing. The goal is to design a study that can test these competing ideas fairly.
"""

INSTRUCTION_AFTER_PROBLEM_SOLVING_STIMULUS_OPENING = """
In the previous activity, you worked with a research problem about social media use and anxiety. Several communication researchers had different ideas about why students who use social media heavily may report higher anxiety. One researcher focused on the amount of social media use, another focused on the mode of use, and a third pointed out that students may already differ in academic stress.

The goal was not to decide which researcher sounded most convincing. The goal was to design a study that can test these competing ideas fairly.
"""

INSTRUCTIONAL_STIMULUS_BEFORE_FIGURE = """
### Common Mistakes and Better Design Choices

Many first study ideas are useful starting points but are still incomplete. A common first idea is to compare students who already use social media heavily with students who use it less, and then measure anxiety once at the end. This idea addresses the topic, but it does not yet give researchers a strong way to test the competing explanations.

The table below shows four common weaknesses in first study ideas and the stronger design choices they point toward.

| Common incomplete idea | Stronger design choice |
| --- | --- |
| The study does not include clear comparison conditions. For example, it may focus only on heavy users, or it may compare heavy users with everyone else without representing the different suggestions clearly. | Include comparison conditions that make the researchers' suggestions testable. Participants should be placed in conditions that allow the study to compare different amounts of social media use and different modes of use. |
| The study changes more than one important feature at the same time. For example, it may compare heavy passive users with light active users, so amount of use and mode of use are mixed together. | Vary the focal factors systematically. A fair design changes one feature at a time across conditions, so researchers can see whether amount of use, mode of use, or their combination matters. |
| The study measures anxiety only once, after the social media activity. This makes it hard to know whether groups were already different before the study began. | Measure anxiety before and after the activity. A before-study measure and an after-study measure allow researchers to examine change, not only final differences. |
| The study ignores a relevant background factor. For example, students who already experience more academic stress may also report more anxiety, regardless of the social media condition. | Use a short questionnaire to measure a relevant control variable, such as baseline academic stress. This helps researchers take important background differences into account when interpreting the results. |

These design choices matter because they make the study more diagnostic. They help researchers separate competing explanations instead of treating all differences between students as if they came from social media use itself.

### A Clear Experimental Design

One clear way to test the competing ideas is a `2 x 2 factorial design`. This means that the study includes two factors, and each factor has two versions. Combining the two factors creates four experimental conditions.
"""

CANONICAL_SOLUTION_FIGURE_PATH = "assets/social-media-anxiety-canonical-solution.png"
CANONICAL_SOLUTION_FIGURE_CAPTION = (
    "Canonical solution of the social-media/anxiety problem presented during instruction."
)

INSTRUCTIONAL_STIMULUS_AFTER_FIGURE = """
The figure summarizes the full design. The middle panel crosses the two factors: amount of social media use and mode of social media use. The boxes around the panel show the other parts of the study that make the design interpretable: anxiety is measured before and after the social-media activity, and academic stress is measured with a questionnaire so it can be considered when interpreting the results.

In this problem, the two factors are:

**Factor A: Amount of social media use**

- `A1`: High social media exposure
- `A2`: Low social media exposure

**Factor B: Mode of social media use**

- `B1`: Passive browsing
- `B2`: Active interaction

These two factors create four conditions:

| Condition | Amount of social media use | Mode of social media use |
| --- | --- | --- |
| 1 | High exposure | Passive browsing |
| 2 | Low exposure | Passive browsing |
| 3 | High exposure | Active interaction |
| 4 | Low exposure | Active interaction |

Participants would be assigned to one of these four conditions. This lets researchers compare high and low exposure while also comparing passive and active use.

The study should also include three types of measurement:

- a before-study measure of anxiety
- an after-study measure of anxiety
- a short questionnaire measuring a relevant control variable, such as baseline academic stress

The before-study and after-study measures help researchers examine whether anxiety changes. The questionnaire helps researchers see whether a background factor, such as academic stress, may also be related to anxiety. Together, these parts make the design stronger than a simple one-time comparison between students who already use social media in different ways.
"""

RSM_COUNT_PROMPT = """
Thinking only about the problem-solving phase you just completed:

How many meaningfully different study-design ideas did you seriously consider before submitting your study ideas?
"""

RSM_COUNT_OPTIONS = ("1 idea", "2 ideas", "3 ideas", "4 or more ideas")
