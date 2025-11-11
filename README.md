+++POS Project+++
------------------
+ API
	- Flask
	- Sqlite, Mysql, PostgreSQL (migration)
	- Auth (token base)
+ FrontEnd
	- Angular v20
------------------
+ branch
	- id(pk)
	- name (varchar)*
	- location (varchar)*
	- logo(varchar)
	- phone(varchar)
+ user
	- id(pk)
	- branch_id(fk)*
	- user_name(varchar)*
	- password(varchar)*
	- profile(varchar)
+ category
	- id(pk)
	- name (varchar)*	
	- image(varchar)
+ product
	- id(pk)
	- name (varchar)*	
	- category_id(fk)*
	- cost(decimal)*
	- price(decimal)*
	- image(varchar)
+ customer
	- id(pk)
	- name (varchar)*	
+ sale
	- id(pk)
	- date_time(datetime)*
	- user_id(fk)*
	- customer_id(fk)*
	- total(decimal)*
	- paid(decimal)*
	- remark(varchar)
+ sale_item
	- id(pk)
	- sale_id(fk)*
	- product_id(fk)*
	- qty(int)*
	- cost(decimal)*
	- price(decimal)*
	- total(decimal)*
# SU3_POS_API
