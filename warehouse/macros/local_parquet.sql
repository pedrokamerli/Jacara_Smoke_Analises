{% macro local_parquet(file_name) %}
    read_parquet('{{ env_var("JACARE_DATA_DIR", "data/processed") | replace("'", "''") }}/{{ file_name }}')
{% endmacro %}
