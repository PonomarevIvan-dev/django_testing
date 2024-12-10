"""
Модуль тестов для проверки маршрутов приложения заметок.

Содержит тесты, проверяющие доступность маршрутов, их поведение
для авторизованных и неавторизованных пользователей, а также
корректность обработки данных.
"""
from http import HTTPStatus

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from pytils.translit import slugify

from notes.models import Note
from notes.forms import WARNING

User = get_user_model()


class TestRoutes(TestCase):
    """Тесты для проверки маршрутов и функциональности приложения заметок."""

    @classmethod
    def setUpTestData(cls):
        """Настройка данных, общих для всех тестов в этом классе."""
        cls.author = User.objects.create(username='author')
        cls.author_client = Client()
        cls.author_client.force_login(cls.author)

        cls.auth_user = User.objects.create(username='auth_user')
        cls.auth_user_client = Client()
        cls.auth_user_client.force_login(cls.auth_user)

        cls.note = Note.objects.create(
            title='Заголовок',
            text='Текст',
            slug='test-slug',
            author=cls.author,
        )

        cls.data = {
            'title': 'Новый заголовок',
            'text': 'Новый текст',
            'slug': 'new-slug',
        }

        cls.NOTES_ADD_URL = reverse('notes:add')
        cls.NOTES_SUCCESS_URL = reverse('notes:success')
        cls.LOGIN_URL = reverse('users:login')

    def assert_note_equal(self, note, data):
        """Вспомогательный метод для проверки атрибутов заметки."""
        self.assertEqual(note.title, data['title'])
        self.assertEqual(note.text, data['text'])
        self.assertEqual(note.slug, data['slug'])

    def test_user_can_create_note(self):
        """Залогиненный пользователь может создать заметку."""
        response = self.author_client.post(self.NOTES_ADD_URL, data=self.data)
        self.assertRedirects(response, self.NOTES_SUCCESS_URL)
        self.assertEqual(Note.objects.count(), 2)
        new_note = Note.objects.exclude(id=self.note.id).get()
        self.assertNoteEqual(new_note, self.data)
        self.assertEqual(new_note.author, self.author)

    def test_anonymous_user_cant_create_note(self):
        """Анонимный пользователь не может создать заметку."""
        response = self.client.post(self.NOTES_ADD_URL, self.data)
        expected_url = f'{self.LOGIN_URL}?next={self.NOTES_ADD_URL}'
        self.assertRedirects(response, expected_url)
        self.assertEqual(Note.objects.count(), 1)

    def test_not_unique_slug(self):
        """Невозможно создать две заметки с одинаковым slug."""
        response = self.author_client.post(self.NOTES_ADD_URL, data={
            'title': 'Другой заголовок',
            'text': 'Другой текст',
            'slug': self.note.slug,
        })
        self.assertFormError(response, 'form', 'slug',
                             errors=(self.note.slug + WARNING))
        self.assertEqual(Note.objects.count(), 1)

    def test_empty_slug(self):
        """Если не заполнен slug, то он формируется автоматически."""
        self.data.pop('slug')
        response = self.author_client.post(self.NOTES_ADD_URL, self.data)
        self.assertRedirects(response, self.NOTES_SUCCESS_URL)
        self.assertEqual(Note.objects.count(), 2)
        new_note = Note.objects.exclude(id=self.note.id).get()
        self.assertEqual(new_note.slug, slugify(self.data['title']))

    def test_author_can_delete_note(self):
        """Пользователь может удалять свои заметки."""
        url = reverse('notes:delete', args=(self.note.slug,))
        response = self.author_client.post(url)
        self.assertRedirects(response, self.NOTES_SUCCESS_URL)
        self.assertEqual(Note.objects.count(), 0)

    def test_other_user_cant_delete_note(self):
        """Пользователь не может удалять чужие заметки."""
        url = reverse('notes:delete', args=(self.note.slug,))
        response = self.auth_user_client.post(url)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.assertEqual(Note.objects.count(), 1)

    def test_author_can_edit_note(self):
        """Пользователь может редактировать свои заметки."""
        url = reverse('notes:edit', args=(self.note.slug,))
        response = self.author_client.post(url, self.data)
        self.assertRedirects(response, self.NOTES_SUCCESS_URL)
        self.note.refresh_from_db()
        self.assertNoteEqual(self.note, self.data)

    def test_other_user_cant_edit_note(self):
        """Пользователь не может редактировать чужие заметки."""
        url = reverse('notes:edit', args=(self.note.slug,))
        response = self.auth_user_client.post(url, self.data)
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)
        self.note.refresh_from_db()
        self.assertNotEqual(self.note.title, self.data['title'])
        self.assertNotEqual(self.note.text, self.data['text'])
        self.assertNotEqual(self.note.slug, self.data['slug'])
