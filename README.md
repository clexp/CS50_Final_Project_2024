# Online note tracking tool

#### Video Demo: <URL HERE>

#### Description: This a personal tool I wrote to track notes online.

This is meant to replace the orginal idea, which was unfeasible in a reasonable time frame. For the submitted project, please skip to line 270. For the Original project, see lines 10-270 and see the folder marked original_project. Please note the Original Project was well over twice the size you see here, but due to a water accident there was a substantial data loss.

=======================================================

#######################################################
#######################################################
####### ########
####### ORIGINAL PROJECT ########
####### STARTS HERE ########
####### ########
#######################################################
#######################################################

# Web sql table visualizer

#### Video Demo: <URL HERE>

#### Description: A tool that uses your SQL .schema text to draw your table tree for design and debugging

##### Scope and Specification

This project allows you to visualize the layout of your database.db schema.

You can either import a text file or copy and paste into the text box.

It will graphically render the schema to help show the relationships.

It does not really need a backend, so there is no data control on the server.

You should be able to drag the tables around, and see the links between tables.

This layout should help you comprehend your database, and resolve misunderstandings. This in turn should help resolve trouble shooting, help build understanding and therefore also the building of better queries. And solve duck theft.

Stretch goal 1: You should be able to see problems, and correct them graphically. The schema will auto update, and you should be able to cut and paste the schema or download it as an initial database.db. This will turn it into a simple Database Architecture tool.

#### Implementation:

For converting text to graphical shape I considered python libraries svgwrite, and also pyscript. It also meant getting familiar with the canvas javascript api. I also had a look at the Brython Library.

###### svgwrite

https://pypi.org/project/svgwrite/
https://svgwrite.readthedocs.io/en/latest/
https://iosoft.blog/2019/02/26/python-graphics-svg/

###### brython

https://codehs.com/tutorial/joianderson/how-to-use-python-graphics-on-your-website
https://miupypzwkw-9545709-i.codehs.me/index.html

###### pyscript

https://www.jhanley.com/blog/pyscript-graphics/
https://www.jhanley.com/examples/pyscript/clock.html

###### canvas api

https://www.w3schools.com/graphics/canvas_clock_start.asp
https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API

###### pyglet

https://pyglet.readthedocs.io/en/latest/
https://pyglet.org/

I considered pyglet, but it does not run in the browser.

The canvas api looked most promising as the sql schema lines could be parsed and javascript functions called to draw the images. This could provide a graphical representation of the sql schema. With some clever use of the Javascript, you could make a really nice layout.

The additional feature of the canvas is that it responds to events. It can feed back clicks and mouse movements. This means the shapes can be dragged about the screen. It means you can drag the table images about to arrange them. It also means you can drag lines from table to table, to define links.

It the first instance, maybe the best thing is to just render the tables. Once you can reliably render the tables, you have something you can submit.

If you have loads of time then you can create something that will allow you to render sql from the drawn image.

These are very different problems. Only related by the subject matter.

##### HTML5

https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Drawing_shapes
https://www.w3schools.com/graphics/canvas_intro.asp

This is really helpful and the tool I probably will use it. Requires use of javascript which I do not know, but CS50 has given me a good grounding in programming generally and the skills are transferable. I am a developing software engineer, so this is not a boundary.

W3schools had some excellent basic introduction to canvas element that was very helpfu

##### Javascript

Thankyou to W3schools for some excellent Javacpript tutorials.
https://www.w3schools.com/js/js_intro.asp
There was a really nice 40 min walkthrough example use and micro exercises to get used to the camel case and the DOM syntax.

##### HTML

It became clear you could not use the input box in HTML to capture the database schema. Actually if you want editable text area you need to use the <textarea></textarea> tags, and again W3schools had some excellent resources.
https://www.w3schools.com/tags/tag_textarea.asp

##### Flexbox

Trying to lay things out as a percentage of the screen began to get fiddley and getting it right for screen sizes began taking a lot of time. I read about flex box and how to layout items within <div></div> nested elements. I discovered CSS property flex box that allows you to shape and style the layout with descriptors operating at a higher level than the % and the px. It works for small screens. I learned about setting the flex-basis to 0, so the flex-grow property can be the main control of the width.

##### Document object model

Using javascript I wanted to parse the sql on the client end.

##### Not HTML Canvas.

After some fiddling, canvas worked but it became clear that the canvas is a flat bitmap. Move items requires clearing the screen and redrawing, so updating requires a lot of work. In addition, changing the shape or moving it about would require code for finding the mouse location.
https://www.youtube.com/watch?v=7PYvx8u_9Sk

This code already exists in the 'draggable' html api. You can declare a div as draggable, you just need some functions for the on-click function. The advantage is you can use all the nice css formatting for your box, you do not have to start from scratch.

##### Which Draggable

After sometime messing about with the css draggable property, it became clear there were 2 types of draggable, and I was mixing them up. One had fixed target locations, the other was more manual and could give final x,y positions.

##### The DOM, again.

There were some demonstrations on stack overflow and on w3schools, but I could not make them work, duckdb had limited amounts to say, and the discord has a communication topic size/detail bottleneck. I dived into the MDN networks pages. This is a language type unlike anything I have seen before. I looked about for some DOM tutorials, but found more javascript. The MDN has some sample code. Most of the DOM objects for dragging seem to relate to the type of draggable I do not want. Confusingly, some of the non MDN code used an undeclared dragElement(), which I could not find as a DOM function (?object/?primitive).

##### all the jigsaw pieces, but not in the pattern I want.

so you can make a draggable with undefined end position from here:

but it is by ID and so only the first instance works. I want multiple instances.
This
https://codepen.io/paulobrien/embed/YzjbRWB?
demonstrate multiple instances. This is much closer but I want to instantiate the draggables based on the textarea input.

##### Make the div draggable on creation

The answer was much simpler than I thought. On creation I could pass the div element to the draggable function to make it draggable. I could trigger a new div with each key press. Now I had to clear them and also trigger a new table on string conditions.

##### Regular Expressions

I have had little use for regular expressions. Learning regular expressions is necessary for programming but remains notorious topic. There are some great web based Regex tools which really helped. I used
https://regex101.com/

[
^CREATE TABLE ([a-zA-Z][a-zA-Z$_0-9]_)\(([a-zA-Z][a-zA-Z$_0-9]_) \b(INTEGER|TEXT|FLOAT|BOOLEAN)\b (AUTOINCREMENT )?(NOT NULL )?(UNIQUE )?,
]

##### Building an sql parser

I began to realize this might easily sprawl into full parser, and become a much bigger project than I had intended. I wanted to parse SQL but I was wrong. Thinking I must be able to get a full library I can use to do this, I browsed git hub and found some interesting projects such as :
https://github.com/forward/sql-parser
I read about parsing and about lexicography and abstract syntax trees. I realized a full parser would be well outside the scope of this project. It became clear a full parser was way more than I needed and usually a full size commercial project.
https://www.jooq.org/doc/latest/manual/sql-building/sql-parser/sql-parser-grammar/
I wanted to parse just 'CREATE TABLE' statements, and use this to build a web map of tables. I did not need a full lexical parser, I just needed some smart use of Regex. But I also needed to test strings in the way sqlite would. I needed to find some syntax naming conventions:
https://www.tutlane.com/tutorial/sqlite/sqlite-syntax
https://www3.rocketsoftware.com/rocketd3/support/documentation/Uniface/10/uniface/dbmsSupport/dbmsDrivers/SQLite/concepts/SLE_NamingRules.htm?TocPath=DBMS%20Support%7CDatabase%20Connectors%7CSQLite%7C_____7#:~:text=The%20syntax%20for%20index%20names,character%20must%20be%20a%20letter.
and
https://www.tutlane.com/tutorial/sqlite/sqlite-syntax

##### More regex

In trying to match some expressions in SQL using regex, it became clear regex on it's own was not the complete toolkit. Really good for moderately complex multiple word finds. Not good for a full comprehension of a language.
https://medium.com/@daffl/beyond-regex-writing-a-parser-in-javascript-8c9ed10576a6
And this one really explained it:
https://storytel.tech/parsing-text-input-without-regular-expressions-3e8de68a79a7
Where it talks about finite state. If something could be multiply nested to n depth, or have n terms in a bracket, then it is not finite state and not appropriate for regex.

And in this unbelievable post:
https://stackoverflow.com/questions/1732348/regex-match-open-tags-except-xhtml-self-contained-tags
I saw an interesting reference to Chomsky type 2 and Chomsky type 3 grammar.

I really did need an sql parsing library in javascript. Or in python if I did it server side.

You cannot capture an unknown number of groups.

##### Javascript SQL parsing libraries

reviewing what is out there:
https://www.npmjs.com/package/js-sql-parser
requires NPM, quite a big package
https://github.com/forward/sql-parser/tree/master
also requires npm
https://github.com/dsferruzza/simpleSqlParser
seems simpler to start with but cannot do CREATE TABLE

And this article has almost done what I want what:
https://datastation.multiprocess.io/blog/2022-04-11-sql-parsers.html
just not very clearly for javascript

This one seemed most visible
https://github.com/dsferruzza/simpleSqlParser/tree/master

##### Comment on linguistic parsers.

Every tool into which I type a command: bash, brew, csh, python, HTML (browser), CSS (Browser), Javascript(browser), all interpretors and by logical extension, all compilers must have a substantive instructional parser.

hmmm. That's something to think about.

This means all the big tools out there, developed some sort of language grammar. Well who does this? Humans in community converse adopting each other's patterns, and create languages. All the great communities that developed languages came to agree on a grammar and syntax as part of forming a corporate identity.
I found this
https://craftinginterpreters.com/
I really want to go and try that.

##### Python SQL parsing libraries

If I did not like the javascript ones could I send the input text to the server to parse to an abstract syntax tree in Python instead? There are some python parsing libaries. This one had a good writeup.
https://github.com/pyparsing/pyparsing/
This might be the easiest thing to do.

It seems there are lots of attempts at a generalised parsers in python
https://medium.com/@yifanpan95/open-source-python-sql-parsers-8dcfaf0c896a

this includes the well developed and highly used
https://github.com/pyparsing
Which can be used for parsing all sorts of languages. I would need to use the simple sql parsing example code. Or use the SQL parser built on it:
https://pypi.org/project/simple-ddl-parser/

Is there a straight up python sql parser that is maintained?
This looks the most suitable.
https://pypi.org/project/sqlparse/

##### Can I just take the parser out of sqlite3?

This is on the face of it not a bad idea as it will accurately parse the supplied code in an identical manner to sqlite3, with the need to learn the sqlite3 grammar rules.
Now I 'Know' C, can I just go and find the parsing functions of sqlite3 and import them into my program?
https://sqlite.org/src/doc/trunk/README.md
looks encouraging. The source code tour was nicely indicative of where to start. It is not on github, and built with fossil, it's own version system, but also wiki, forum and home page and tech notes all in one. You can download the files and unpack. Inspecting them locally and reading the docs indicate I need to use a parser builder called lemon, that will use grammar file to build the parser C module. Lemon is an equivalent to parser flex and bison or yacc and lex. It is a parser generator, and is given a rule file.

The files do not have the actual parse.c file, that is generated when you run lemon.

So how can I use this? I would need some sort of api/abi to let the javascript, or python talk to the parser.c. I would need to use lemon to build the parser.c. I would need to learn lemon and to learn how to make a python or javascript module. This is a lot of work.

SQLite and Lemon are very well documented. The material however is aimed at seasoned programmers. It does not appear to have onroading for outsiders of the community. The ideal solution would be to use the SQLite c parser. Given the availability of good libraries for Python and Javascript, using SQLite3 is just too expensive

##### Coming back to Python's 'sqlparser' library

It seems like the right balance is to use a library that parses SQL, in a language with which I am familiar.

Using this library there are 2 nice examples of using the parser to get column names in a CREATE TABLE statement, and also to get tokens from a SELECT query. The CREATE TABLE statement stripped out and handed back known tokens. It could not (out of the box) correctly handle the FOREIGN KEY token, which is a key part of this project. Also it seems to hand back the tokens as text types of known content, be it the SQL keywords.

Is this going to work. I needed more python library options.
this post
https://medium.com/@yifanpan95/open-source-python-sql-parsers-8dcfaf0c896a
revealed to me a bunche of very competant looking python SQL parsing libraries. Of those, sqlfluff and sqloxide got my interest. slqfluff looks possibly a little over powered but very capable. SQLoxide looks capable but also very very fast, written in rust. Both of these would be on the server in python. It feels like fun to play with the new fast thing, but why do I want it to be fast if I am running on the server? surely if I wanted speed I want it to run in the browser, and use wasm? SQLfluff is more of a linter as the name implies, it can be configured to parse. SQLoxide outputs pure python types, so it can be nicely used on the server.

I am over 1000 words and I have not settled on which library I am going to use.

##### SQLoxide

Trying out sqloxide, it seems to comprehensively parse select, create table and join. The output is a relatively complex nested object structure. But very usable. Now I need to thread this into the webapp.

SQLoxide is pretty serious library. It is a python wrapper round the rust library. The original rust library seems to comprehensively cover a number of rust dialect and the wrapper returns just python objects.

Looking through the SQLoxide output, the objects are variably nested. It takes some parsing at the outset to make sense of the objects, but the objects are not text any more and are meaningful SQL tokens. I am just looking at a small token of the SQL for drawing tables, and I need a way to hand back a tidied nested object to the app.py to generate the html. With a variably nested table, I think I need recursion, not looping.

Eventaully it worked. I had a deeply nested set of python objects from SQLoxide, and some python to fish out the key points. what next?

##### Browser rendering, server rendering?

I could now use some jinja, css and html to render the map in the server, and send it to the browser. Or I could package it up as json and get the browser to do it.

Either way I needed an algorithm, that given a set objects, could lay them out on screen in a sensible pattern. I asked chatGPT.

Up to this point I had asked ChatGPT very little. I had some discussions with DDB, for both architecture and implementation. DDB did seem to prefer technical detail, but architectural decisions was a little more vague. ChatGPT first listed the methods for doing this and in was clear immediately which I had to use. Then it came up with some really competant suggestions for libraries to lay objects out on screen for python, and javascript. I tried them out, and they were impressive, some produceing a tiny local web server and others simply popping a graphic in a window. This made 6 things cross my mind.

1. This was a really good find. It might only be correct up to nov 2022, but a competant library in Nov 2022 is still a competant library in Feb of 2024.
2. My googles searched for a java sql tool were not very fruitful, perhaps I should have asked ChatGPT first. Or go back and see what ChatGPT has to say.
3. There have been several instances where due to SEO, I am not able to find something on Google that someone else is. My wife and I have both had this. Does ChatGPT function better as a reference/librarian of the internet than a simple google search?
4. Why did DDB not make these suggestions? Is this part of the prompt engineering? Deliberately not funnel students into a library preference?
5. The python libraries would put graphics on the servers desktop, and these objects could not be packaged up and sent over to the client as the browser has no python interpretor and packages.
6. ChatGPT did make some technical suggestions and provided trial code. It suggested inaccurate code which did not run. On prompting it made suggestion of change which then aslo indicated not understanding types. When explained, ChatGPT continued to make this mistake. I resolved the issue without ChatGPT assistance. Other commentators indicated similar experience.

###### Server side

If I use python on the servere side to make a force-directed layout, I need to have some way of indicating approximate x y values in the parent div. These may need to be ratios of the parent div, and the size of each div. Is is possible? It may still need some coaxing from javascript in the browser.

##### Browser Side

If I am working with javascript in the browser, I will need to send some json (using ajax?) to the javascript? If I am doing this, could I have parsed the whole lot in javascript anyway? There is an excellent js library called cytospace for these sorts of graphs. The ecosystem must have some sort of good sql parser?

## Cut to something managemeable

This project became too big too quickly. It covered too many areas which on their own were pretty big, and required learning two greater number of new technology to greater depth. Ordinary life took over and the project had to be parked for sometime. Now reviewing it several months later I realise this project would not outlive my time on CS 50 and so it does not meet the CS50 project intentions.

I realise this project would not outlive my time on CS 50 and so it does not meet the CS50 project intentions.

What I do want is an online note logger. This would outlive my time on CS 50. An online tool that allows me to add notes search notes edit and delete notes is personal and specific to me. I would use indefinitely so this would outlive CS50 for me at this point. I'd like to change the project to an online note tracking too

#######################################################
#######################################################
####### ########
####### ORIGINAL PROJECT ########
####### ENDS HERE ########
####### ########
#######################################################
#######################################################

=======================================================

#######################################################
#######################################################
####### ########
####### FINAL PROJECT ########
####### STARTS HERE ########
####### ########
#######################################################
#######################################################

# Final Project

### What will it do, Features, how will it be done?

1. At first it will be a simple learning notes logger with CRUD features.
2. It should have some search functionality added. This is the minimum viable product.

Stretch: 3. I would like to added some sort of flash card function to it, which I may or may not complete in the time available 4. The flash card function should select some cards, based on weakest and oldest recall, and keep a score for memorization for each note 5. This should be accessible online and so should have a web front end. The most likely tools here are flask and sqlite.

### What new skills will you need to aquire and what topics will you need to research?

In my daily life I have learnt HTML, CSS, Flask, SQLite on at least 2 occasions, and then never used them. This will be an exercise in formalising these rusty skills.
I have expent my time budget for research in the original project, so I will need to stick to known areas mainly.
I will work alone.

### What is a good outcome, a better outcome, the best outcome?

#### Good outcome:

A one user website that allows CRUD functions on a database of learning notes.
It is local online.
It can be searched.
It is text and bullet points.
Each note may or may not have a flashcard function with it.
There is a flashcard function for spaced repetition, selecting random cards
This will be the target to submit, it is a minimum viable product.

#### Better outcome:

A single user website that allows CRUD functions on a database of learning notes, notes have flags/tags, and links to other notes.
It is online and can be acessed from anywhere.
It can be searched, with better functionality for searching flags/tags.
It is text and bullet points, and can hold images and web links.
Each note may or may not have a flashcard function with it.
There is a flashcard function for spaced repetition, untested cards, recently added cards, and poorly memorized cards.
Each flash card test result is kept.
This will be the target 'beyond CS50'. I am a knowledge worker in my 40's and need memorization support.

#### Best outcome

A Multi user website that allows CRUD functions on a database of learning notes, notes have flags/tags, and links to other notes.
It is online and can be acessed from anywhere, it is desktop/mobile friendly
It can be searched, with better functionality for searching flags/tags, linked notes are briefly listed under results.
It is text and bullet points, and can hold images and web links.
Each note has a flashcard function derived from a LLM, which is different each time, but tests the same card/note.
There is a flashcard function for spaced repetition, untested cards, recently added cards, and poorly memorized cards.
Each flash card test result is kept There is some sort of progress graphing tool.
This will be the target to support my children in their learning endeavours 'beyond CS50'.

### Git.

I want to use git and github for this. I can't do this on the cs50 remote vm. This means I will get to step one and submit, and use git and github thereafter locally.

## Milestones

1. Get a web page displayed through flask. Done
2. Make a couple of pages and click between them. Done
3. Take data in the data form. Done
4. Write data to database and show it is there. Done
5. Show the most recent 10 on search page. Done
6. Take a query and display results. Done
7. Make the query list page clickable to show a note. Done
8. Make an edit button on the note page. Done
9. Make an edit note page and update the note. Done
10. Make the content window bigger. Done
11. Add Subject, Topic, Date. Done
12. Make a delete button on search, view and edit Done
13. Search by any column Done
14. Search by multiple columns. Done
15. Add Question with true and false answers to the note. Done
16. Make a test set builder of Random questions. Done
17. Run tests. Done
18. Stylize it to look less 'Finance50'
    THIS COMPLETES THE MVP, SUBMIT AT THIS STAGE
    OR SUBMIT 30-11-24
19. Export the project.
20. Set up a GitHub repo.
21. Make the project video.
22. Submit the form.
23. Submit the project.
24. Collect the certificate
    AIM TO COMPLETE 'BETTER' FOR PERSONAL USE
25. Collect test results
26. Graph the test results by topic/ mem note.
27. Add optional Url web link to each note
28. Add Flags to the database.
29. Make a flag editor as a subset of new and edit note.
30. Modify the test set builder for memorization.
    ??. Error handling.
    (Poorly memorized, not recently seen, and untested)
    AIM TO COMPLETE 'BEST' FOR SHARED USE
31. Consider prettifying.
32. Make it multi-user.
33. Add links between Notes.
34. Use links between notes it the test sets.
35. Add image upload to each note.
36. Use an LLM (local or remote) to generate q sets.
37. Test against existing questions.
38. Use a Multi-Modal-Model to make Questions from images.
39. Put it on a remotely accessible server.
40. Share it with others.
41. People can save out and load in mem notes sets.
